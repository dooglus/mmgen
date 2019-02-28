#!/bin/bash
# Tested on Linux, MinGW-64
# MinGW's bash 3.1.17 doesn't do ${var^^}

trap 'echo -e "${GREEN}Exiting at user request$RESET"; exit' INT

umask 0022

export MMGEN_TEST_SUITE=1
export MMGEN_NO_LICENSE=1
export PYTHONPATH=.
test_py='test/test.py -n'
objtest_py='test/objtest.py'
tooltest_py='test/tooltest.py'
tooltest2_py='test/tooltest2.py --names'
gentest_py='test/gentest.py'
scrambletest_py='test/scrambletest.py'
mmgen_tool='cmds/mmgen-tool'
mmgen_keygen='cmds/mmgen-keygen'
python='python3'
rounds=100 rounds_low=20 rounds_spec=500 sha_rounds=500 gen_rounds=10
monero_addrs='3,99,2,22-24,101-104'

dfl_tests='obj sha256 alts monero eth autosign btc btc_tn btc_rt bch bch_rt ltc ltc_tn ltc_rt tool tool2 gen'
add_tests='autosign_minimal autosign_live'

PROGNAME=$(basename $0)
while getopts hbCfiIlOpRtvV OPT
do
	case "$OPT" in
	h)  printf "  %-16s Test MMGen release\n" "${PROGNAME}:"
		echo   "  USAGE:           $PROGNAME [options] [branch] [tests]"
		echo   "  OPTIONS: '-h'  Print this help message"
		echo   "           '-b'  Buffer keypresses for all invocations of 'test/test.py'"
		echo   "           '-C'  Run tests in coverage mode"
		echo   "           '-f'  Speed up the tests by using fewer rounds"
		echo   "           '-i'  Create and install Python package, then run tests"
		echo   "           '-I'  Install the package only; don't run tests"
		echo   "           '-l'  List the test name symbols"
		echo   "           '-O'  Use pexpect.spawn rather than popen_spawn for applicable tests"
		echo   "           '-p'  Pause between tests"
		echo   "           '-R'  Don't remove temporary files after program has exited"
		echo   "           '-t'  Print the tests without running them"
		echo   "           '-v'  Run test/test.py with '--exact-output' and other commands with '--verbose' switch"
		echo   "           '-V'  Run test/test.py and other commands with '--verbose' switch"
		echo   "  AVAILABLE TESTS:"
		echo   "     obj      - data objects"
		echo   "     sha256   - MMGen sha256 implementation"
		echo   "     alts     - operations for all supported gen-only altcoins"
		echo   "     monero   - operations for Monero"
		echo   "     eth      - operations for Ethereum"
		echo   "     autosign - autosign"
		echo   "     btc      - bitcoin"
		echo   "     btc_tn   - bitcoin testnet"
		echo   "     btc_rt   - bitcoin regtest"
		echo   "     bch      - bitcoin cash (BCH)"
		echo   "     bch_rt   - bitcoin cash (BCH) regtest"
		echo   "     ltc      - litecoin"
		echo   "     ltc_tn   - litecoin testnet"
		echo   "     ltc_rt   - litecoin regtest"
		echo   "     tool     - tooltest (all supported coins)"
		echo   "     tool2    - tooltest2 (all supported coins)"
		echo   "     gen      - gentest (all supported coins)"
		echo   "  By default, all tests are run"
		exit ;;
	b)  test_py+=" --buf-keypress" ;;
	C)  mkdir -p 'test/trace'
		touch 'test/trace.acc'
		test_py+=" --coverage"
		tooltest_py+=" --coverage"
		tooltest2_py+=" --fork --coverage"
		scrambletest_py+=" --coverage"
		python="python3 -m trace --count --file=test/trace.acc --coverdir=test/trace"
		objtest_py="$python $objtest_py"
		gentest_py="$python $gentest_py"
		mmgen_tool="$python $mmgen_tool"
		mmgen_keygen="$python $mmgen_keygen" ;&
	f)  rounds=2 rounds_low=2 rounds_spec=10 sha_rounds=40 gen_rounds=2 monero_addrs='3,23' ;;
	i)  INSTALL=1 ;;
	I)  INSTALL_ONLY=1 ;;
	l)  echo -e "Default tests:\n  $dfl_tests"
		echo -e "Additional tests:\n  $add_tests"
		exit ;;
	O)  test_py+=" --pexpect-spawn" ;;
	p)  PAUSE=1 ;;
	R)  NO_TMPFILE_REMOVAL=1 ;;
	t)  TESTING=1 ;;
	v)  EXACT_OUTPUT=1 test_py+=" --exact-output" ;&
	V)  VERBOSE=1 [ "$EXACT_OUTPUT" ] || test_py+=" --verbose"
		tooltest_py+=" --verbose" tooltest2_py+=" --verbose" gentest_py+=" --verbose" mmgen_tool+=" --verbose"
		scrambletest_py+=" --verbose" ;;
	*)  exit ;;
	esac
done

[ "$EXACT_OUTPUT" -o "$VERBOSE" ] || objtest_py+=" -S"

shift $((OPTIND-1))

REFDIR='test/ref'
if uname -a | grep -qi mingw; then SUDO='' MINGW=1; else SUDO='sudo' MINGW=''; fi
[ "$MINGW" ] || RED="\e[31;1m" GREEN="\e[32;1m" YELLOW="\e[33;1m" RESET="\e[0m"

[ "$INSTALL" ] && {
	BRANCH=$1; shift
	BRANCHES=$(git branch)
	FOUND_BRANCH=$(for b in ${BRANCHES/\*}; do [ "$b" == "$BRANCH" ] && echo ok; done)
	[ "$FOUND_BRANCH" ] || { echo "Branch '$BRANCH' not found!"; exit; }
}

set -e

check() {
	[ "$BRANCH" ] || { echo 'No branch specified.  Exiting'; exit; }
	[ "$(git diff $BRANCH)" == "" ] || {
		echo "Unmerged changes from branch '$BRANCH'. Exiting"
		exit
	}
	git diff $BRANCH >/dev/null 2>&1 || exit
}
uninstall() {
	set +e
	eval "$SUDO ./scripts/uninstall-mmgen.py"
	[ "$?" -ne 0 ] && { echo 'Uninstall failed, but proceeding anyway'; sleep 1; }
	set -e
}
install() {
	set -x
	eval "$SUDO rm -rf .test-release"
	git clone --branch $BRANCH --single-branch . .test-release
	(
		cd .test-release
		./setup.py sdist
		mkdir pydist && cd pydist
		if [ "$MINGW" ]; then unzip ../dist/mmgen-*.zip; else tar zxvf ../dist/mmgen-*gz; fi
		cd mmgen-*
		eval "$SUDO ./setup.py clean --all"
		[ "$MINGW" ] && ./setup.py build --compiler=mingw32
		eval "$SUDO ./setup.py install --force"
	)
	set +x
}
do_test() {
	set +x
	for i in "$@"; do
		LS='\n'
		[ "$TESTING" ] && LS=''
		echo $i | grep -q 'gentest' && LS=''
		echo -e "$LS${GREEN}Running:$RESET $YELLOW$i$RESET"
		[ "$TESTING" ] || eval "$i" || {
			echo -e $RED"Test '$CUR_TEST' failed at command '$i'"$RESET
			exit
		}
	done
}
i_obj='Data object'
s_obj='Testing data objects'
t_obj=(
	"$objtest_py --coin=btc"
	"$objtest_py --coin=btc --testnet=1"
	"$objtest_py --coin=ltc"
	"$objtest_py --coin=ltc --testnet=1")
f_obj='Data object test complete'

i_sha256='MMGen sha256 implementation'
s_sha256='Testing sha256 implementation'
t_sha256=("$python test/sha256test.py $sha_rounds")
f_sha256='Sha256 test complete'

i_alts='Gen-only altcoin'
s_alts='The following tests will test generation operations for all supported altcoins'
t_alts=(
	"$scrambletest_py"
	"$test_py ref_alt"
	"$gentest_py --coin=btc 2 $rounds"
	"$gentest_py --coin=btc --type=compressed 2 $rounds"
	"$gentest_py --coin=btc --type=segwit 2 $rounds"
	"$gentest_py --coin=btc --type=bech32 2 $rounds"
	"$gentest_py --coin=ltc 2 $rounds"
	"$gentest_py --coin=ltc --type=compressed 2 $rounds"
	"$gentest_py --coin=ltc --type=segwit 2 $rounds"
	"$gentest_py --coin=ltc --type=bech32 2 $rounds"
	"$gentest_py --coin=etc 2 $rounds"
	"$gentest_py --coin=eth 2 $rounds"
	"$gentest_py --coin=zec 2 $rounds"
	"$gentest_py --coin=zec --type=zcash_z 2 $rounds_spec"

	"$gentest_py --coin=btc 2:ext $rounds"
	"$gentest_py --coin=btc --type=compressed 2:ext $rounds"
	"$gentest_py --coin=btc --type=segwit 2:ext $rounds"
	"$gentest_py --coin=ltc 2:ext $rounds"
	"$gentest_py --coin=ltc --type=compressed 2:ext $rounds"
#	"$gentest_py --coin=ltc --type=segwit 2:ext $rounds" # pycoin generates old-style LTC Segwit addrs
	"$gentest_py --coin=etc 2:ext $rounds"
	"$gentest_py --coin=eth 2:ext $rounds"
	"$gentest_py --coin=zec 2:ext $rounds"
	"$gentest_py --coin=zec --type=zcash_z 2:ext $rounds_spec"

	"$gentest_py --all 2:pycoin $rounds_low"
	"$gentest_py --all 2:pyethereum $rounds_low"
	"$gentest_py --all 2:keyconv $rounds_low"
	"$gentest_py --all 2:zcash_mini $rounds_low")
if [ "$MINGW" ]; then
	t_alts[13]="# MSWin platform: skipping zcash z-addr generation and altcoin verification with third-party tools"
	i=14 end=${#t_alts[*]}
	while [ $i -lt $end ]; do unset t_alts[$i]; let i++; done
fi
f_alts='Gen-only altcoin tests completed'

if [ "$MINGW" ]; then
	TMPDIR='/tmp/mmgen-test-release'
else
	TMPDIR='/tmp/mmgen-test-release-'$(cat /dev/urandom | base32 - | head -n1 | cut -b 1-16)
fi
mkdir -p $TMPDIR

i_monero='Monero'
s_monero='Testing key-address file generation and wallet creation and sync operations for Monero'
s_monero='The monerod (mainnet) daemon must be running for the following tests'
t_monero=(
"mmgen-walletgen -q -r0 -p1 -Llabel --outdir $TMPDIR -o words"
"$mmgen_keygen -q --accept-defaults --outdir $TMPDIR --coin=xmr $TMPDIR/*.mmwords $monero_addrs"
'cs1=$(mmgen-tool -q --accept-defaults --coin=xmr keyaddrfile_chksum $TMPDIR/*-XMR*.akeys)'
"$mmgen_keygen -q --use-old-ed25519 --accept-defaults --outdir $TMPDIR --coin=xmr $TMPDIR/*.mmwords $monero_addrs"
'cs2=$(mmgen-tool -q --accept-defaults --coin=xmr keyaddrfile_chksum $TMPDIR/*-XMR*.akeys)'
'[ "$cs1" == "$cs2" ] || false'
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR keyaddrlist2monerowallets $TMPDIR/*-XMR*.akeys addrs=23"
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR keyaddrlist2monerowallets $TMPDIR/*-XMR*.akeys addrs=103-200"
'rm $TMPDIR/*-MoneroWallet*'
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR keyaddrlist2monerowallets $TMPDIR/*-XMR*.akeys"
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR syncmonerowallets $TMPDIR/*-XMR*.akeys addrs=3"
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR syncmonerowallets $TMPDIR/*-XMR*.akeys addrs=23-29"
"$mmgen_tool -q --accept-defaults --outdir $TMPDIR syncmonerowallets $TMPDIR/*-XMR*.akeys"
)
[ "$MINGW" ] && {
	t_monero[2]="# MSWin platform: skipping Monero wallet creation and sync tests; NOT verifying key-addr list"
	i=3 end=${#t_monero[*]}
	while [ $i -lt $end ]; do unset t_monero[$i]; let i++; done
}
[ "$monero_addrs" == '3,23' ] && {
	unset t_monero[12]
	unset t_monero[7]
	unset t_monero[3]
}
f_monero='Monero tests completed'

i_eth='Ethereum'
s_eth='Testing transaction and tracking wallet operations for Ethereum and Ethereum Classic'
t_eth=(
	"$test_py --coin=eth ref_tx_chk"
	"$test_py --coin=eth --testnet=1 ref_tx_chk"
	"$test_py --coin=etc ref_tx_chk"
	"$test_py --coin=eth ethdev"
	"$test_py --coin=etc ethdev"
)
f_eth='Ethereum tests completed'

i_autosign='Autosign'
s_autosign='The bitcoin, bitcoin-abc and litecoin mainnet and testnet daemons must be running for the following test'
t_autosign=("$test_py autosign")
f_autosign='Autosign test complete'

i_autosign_minimal='Autosign Minimal'
s_autosign_minimal='The bitcoin mainnet and testnet daemons must be running for the following test'
t_autosign_minimal=("$test_py autosign_minimal")
f_autosign_minimal='Autosign Minimal test complete'

i_autosign_live='Autosign Live'
s_autosign_live="The bitcoin mainnet and testnet daemons must be running for the following test\n"
s_autosign_live+="${YELLOW}Mountpoint, '/etc/fstab' and removable device must be configured "
s_autosign_live+="as described in 'mmgen-autosign --help'${RESET}"
t_autosign_live=("$test_py autosign_live")
f_autosign_live='Autosign Live test complete'

i_btc='Bitcoin mainnet'
s_btc='The bitcoin (mainnet) daemon must both be running for the following tests'
t_btc=(
	"$test_py"
	"$test_py --segwit dfl_wallet main ref ref_files"
	"$test_py --segwit-random dfl_wallet main"
	"$test_py --bech32 dfl_wallet main ref ref_files"
	"$python scripts/compute-file-chksum.py $REFDIR/*testnet.rawtx >/dev/null 2>&1")
f_btc='You may stop the bitcoin (mainnet) daemon if you wish'

i_btc_tn='Bitcoin testnet'
s_btc_tn='The bitcoin testnet daemon must both be running for the following tests'
t_btc_tn=(
	"$test_py --testnet=1"
	"$test_py --testnet=1 --segwit dfl_wallet main ref ref_files"
	"$test_py --testnet=1 --segwit-random dfl_wallet main"
	"$test_py --testnet=1 --bech32 dfl_wallet main ref ref_files")
f_btc_tn='You may stop the bitcoin testnet daemon if you wish'

i_btc_rt='Bitcoin regtest'
s_btc_rt="The following tests will test MMGen's regtest (Bob and Alice) mode"
t_btc_rt=(
	"$test_py regtest"
	)
f_btc_rt='Regtest (Bob and Alice) mode tests for BTC completed'

i_bch='Bitcoin cash (BCH)'
s_bch='The bitcoin cash daemon (Bitcoin ABC) must both be running for the following tests'
t_bch=("$test_py --coin=bch dfl_wallet main ref ref_files")
f_bch='You may stop the Bitcoin ABC daemon if you wish'

i_bch_rt='Bitcoin cash (BCH) regtest'
s_bch_rt="The following tests will test MMGen's regtest (Bob and Alice) mode"
t_bch_rt=("$test_py --coin=bch regtest")
f_bch_rt='Regtest (Bob and Alice) mode tests for BCH completed'

i_ltc='Litecoin'
s_ltc='The litecoin daemon must both be running for the following tests'
t_ltc=(
	"$test_py --coin=ltc dfl_wallet main ref ref_files"
	"$test_py --coin=ltc --segwit dfl_wallet main ref ref_files"
	"$test_py --coin=ltc --segwit-random dfl_wallet main"
	"$test_py --coin=ltc --bech32 dfl_wallet main ref ref_files")
f_ltc='You may stop the litecoin daemon if you wish'

i_ltc_tn='Litecoin testnet'
s_ltc_tn='The litecoin testnet daemon must both be running for the following tests'
t_ltc_tn=(
	"$test_py --coin=ltc --testnet=1"
	"$test_py --coin=ltc --testnet=1 --segwit dfl_wallet main ref ref_files"
	"$test_py --coin=ltc --testnet=1 --segwit-random dfl_wallet main"
	"$test_py --coin=ltc --testnet=1 --bech32 dfl_wallet main ref ref_files")
f_ltc_tn='You may stop the litecoin testnet daemon if you wish'

i_ltc_rt='Litecoin regtest'
s_ltc_rt="The following tests will test MMGen's regtest (Bob and Alice) mode"
t_ltc_rt=("$test_py --coin=ltc regtest")
f_ltc_rt='Regtest (Bob and Alice) mode tests for LTC completed'

i_tool2='Tooltest2'
s_tool2="The following tests will run '$tooltest2_py' for all supported coins"
t_tool2=(
	"$tooltest2_py --quiet --non-coin-dependent"
	"$tooltest2_py --quiet --coin=btc --coin-dependent"
	"$tooltest2_py --quiet --coin=btc --testnet=1 --coin-dependent"
	"$tooltest2_py --quiet --coin=ltc --coin-dependent"
	"$tooltest2_py --quiet --coin=ltc --testnet=1 --coin-dependent"
	"$tooltest2_py --quiet --coin=bch --coin-dependent"
	"$tooltest2_py --quiet --coin=bch --testnet=1 --coin-dependent"
	"$tooltest2_py --quiet --coin=zec --coin-dependent"
	"$tooltest2_py --quiet --coin=zec --type=zcash_z --coin-dependent"
	"$tooltest2_py --quiet --coin=xmr --coin-dependent"
	"$tooltest2_py --quiet --coin=dash --coin-dependent"
	"$tooltest2_py --quiet --coin=eth --coin-dependent"
	"$tooltest2_py --quiet --coin=eth --testnet=1 --coin-dependent"
	"$tooltest2_py --quiet --coin=eth --token=mm1 --coin-dependent"
	"$tooltest2_py --quiet --coin=eth --token=mm1 --testnet=1 --coin-dependent"
	"$tooltest2_py --quiet --coin=etc --coin-dependent")
f_tool2='tooltest2 tests completed'

i_tool='Tooltest'
s_tool="The following tests will run '$tooltest_py' for all supported coins"
t_tool=(
	"$tooltest_py --coin=btc util"
	"$tooltest_py --coin=btc cryptocoin"
	"$tooltest_py --coin=btc mnemonic"
	"$tooltest_py --coin=ltc cryptocoin"
	"$tooltest_py --coin=eth cryptocoin"
	"$tooltest_py --coin=etc cryptocoin"
	"$tooltest_py --coin=dash cryptocoin"
	"$tooltest_py --coin=doge cryptocoin"
	"$tooltest_py --coin=emc cryptocoin"
	"$tooltest_py --coin=zec cryptocoin")

[ "$MINGW" ] || {
	t_tool_len=${#t_tool[*]}
	t_tool[$t_tool_len]="$tooltest_py --coin=zec --type=zcash_z cryptocoin"
}
f_tool='tooltest tests completed'

i_gen='Gentest'
s_gen="The following tests will run '$gentest_py' on mainnet and testnet for all supported coins"
t_gen=(
	"$gentest_py -q 2 $REFDIR/btcwallet.dump"
	"$gentest_py -q --type=segwit 2 $REFDIR/btcwallet-segwit.dump"
	"$gentest_py -q --type=bech32 2 $REFDIR/btcwallet-bech32.dump"
	"$gentest_py -q 1:2 $gen_rounds"
	"$gentest_py -q --type=segwit 1:2 $gen_rounds"
	"$gentest_py -q --type=bech32 1:2 $gen_rounds"
	"$gentest_py -q --testnet=1 2 $REFDIR/btcwallet-testnet.dump"
	"$gentest_py -q --testnet=1 1:2 $gen_rounds"
	"$gentest_py -q --testnet=1 --type=segwit 1:2 $gen_rounds"
	"$gentest_py -q --coin=ltc 2 $REFDIR/litecoin/ltcwallet.dump"
	"$gentest_py -q --coin=ltc --type=segwit 2 $REFDIR/litecoin/ltcwallet-segwit.dump"
	"$gentest_py -q --coin=ltc --type=bech32 2 $REFDIR/litecoin/ltcwallet-bech32.dump"
	"$gentest_py -q --coin=ltc 1:2 $gen_rounds"
	"$gentest_py -q --coin=ltc --type=segwit 1:2 $gen_rounds"
	"$gentest_py -q --coin=ltc --testnet=1 2 $REFDIR/litecoin/ltcwallet-testnet.dump"
	"$gentest_py -q --coin=ltc --testnet=1 1:2 $gen_rounds"
	"$gentest_py -q --coin=ltc --testnet=1 --type=segwit 1:2 $gen_rounds")
f_gen='gentest tests completed'

[ -d .git -a -n "$INSTALL"  -a -z "$TESTING" ] && {
	check
	uninstall
	install
	cd .test-release/pydist/mmgen-*
}
[ "$INSTALL_ONLY" ] && exit

prompt_skip() {
	echo -n "Enter 's' to skip, or ENTER to continue: "; read -n1; echo
	[ "$REPLY" == 's' ] && return 0
	return 1
}

run_tests() {
	for t in $1; do
		eval echo -e \${GREEN}'###' Running $(echo \$i_$t) tests\$RESET
		eval echo -e $(echo \$s_$t)
		[ "$PAUSE" ] && prompt_skip && continue
		CUR_TEST=$t
		eval "do_test \"\${t_$t[@]}\""
		eval echo -e \$GREEN$(echo \$f_$t)\$RESET
	done
}

check_args() {
	for i in $tests; do
		echo "$dfl_tests $add_tests" | grep -q "\<$i\>" || { echo "$i: unrecognized argument"; exit; }
	done
}

tests=$dfl_tests
[ "$*" ] && tests="$*"

check_args
echo "Running tests: $tests"
START=$(date +%s)
run_tests "$tests"
TIME=$(($(date +%s)-START))
MS=$(printf %02d:%02d $((TIME/60)) $((TIME%60)))

[ "$NO_TMPFILE_REMOVAL" ] || rm -rf /tmp/mmgen-test-release-*

echo -e "${GREEN}All OK.  Total elapsed time: $MS$RESET"
