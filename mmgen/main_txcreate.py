#!/usr/bin/env python
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C)2013-2015 Philemon <mmgen-py@yandex.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
mmgen-txcreate: Create a Bitcoin transaction from MMGen- or non-MMGen inputs
                to MMGen- or non-MMGen outputs
"""

import sys
from decimal import Decimal

import mmgen.config as g
from mmgen.Opts import *
from mmgen.license import *
from mmgen.tx import *

help_data = {
	'prog_name': g.prog_name,
	'desc':    "Create a BTC transaction with outputs to specified addresses",
	'usage':   "[opts]  <addr,amt> ... [change addr] [addr file] ...",
	'options': """
-h, --help            Print this help message
-c, --comment-file= f Source the transaction's comment from file 'f'
-d, --outdir=       d Specify an alternate directory 'd' for output
-e, --echo-passphrase Print passphrase to screen when typing it
-f, --tx-fee=       f Transaction fee (default: {g.tx_fee} BTC)
-i, --info            Display unspent outputs and exit
-q, --quiet           Suppress warnings; overwrite files without
                      prompting
-v, --verbose         Produce more verbose output
""".format(g=g),
	'notes': """

Transaction inputs are chosen from a list of the user's unpent outputs
via an interactive menu.

Ages of transactions are approximate based on an average block creation
interval of {g.mins_per_block} minutes.

Addresses on the command line can be Bitcoin addresses or {pnm} addresses
of the form <seed ID>:<number>.

To send all inputs (minus TX fee) to a single output, specify one address
with no amount on the command line.
""".format(g=g,pnm=g.proj_name)
}

wmsg = {
	'too_many_acct_addresses': """
ERROR: More than one address found for account: "%s".
Your "wallet.dat" file appears to have been altered by a non-{pnm} program.
Please restore your tracking wallet from a backup or create a new one and
re-import your addresses.
""".strip().format(pnm=g.proj_name),
	'addr_in_addrfile_only': """
Warning: output address {mmgenaddr} is not in the tracking wallet, which means
its balance will not be tracked.  You're strongly advised to import the address
into your tracking wallet before broadcasting this transaction.
""".strip(),
	'addr_not_found': """
No data for MMgen address {mmgenaddr} could be found in either the tracking
wallet or the supplied address file.  Please import this address into your
tracking wallet, or supply an address file for it on the command line.
""".strip(),
	'addr_not_found_no_addrfile': """
No data for MMgen address {mmgenaddr} could be found in the tracking wallet.
Please import this address into your tracking wallet or supply an address file
for it on the command line.
""".strip(),
	'no_spendable_outputs': """
No spendable outputs found!  Import addresses with balances into your
watch-only wallet using '{pnm}-addrimport' and then re-run this program.
""".strip().format(pnm=g.proj_name.lower()),
	'mixed_inputs': """
NOTE: This transaction uses a mixture of both mmgen and non-mmgen inputs, which
makes the signing process more complicated.  When signing the transaction, keys
for the non-{pnm} inputs must be supplied to '{pnl}-txsign' in a file with the
'--keys-from-file' option.

Selected mmgen inputs: %s
""".strip().format(pnm=g.proj_name,pnl=g.proj_name.lower()),
	'not_enough_btc': """
Not enough BTC in the inputs for this transaction (%s BTC)
""".strip(),
	'throwaway_change': """
ERROR: This transaction produces change (%s BTC); however, no change address
was specified.
""".strip(),
}

def format_unspent_outputs_for_printing(out,sort_info,total):

	pfs  = " %-4s %-67s %-34s %-12s %-13s %-8s %-10s %s"
	pout = [pfs % ("Num","TX id,Vout","Address","MMgen ID",
		"Amount (BTC)","Conf.","Age (days)", "Comment")]

	for n,i in enumerate(out):
		addr = "=" if i.skip == "addr" and "grouped" in sort_info else i.address
		tx = " " * 63 + "=" \
			if i.skip == "txid" and "grouped" in sort_info else str(i.txid)

		s = pfs % (str(n+1)+")", tx+","+str(i.vout),addr,
				i.mmid,i.amt,i.confirmations,i.days,i.label)
		pout.append(s.rstrip())

	return \
"Unspent outputs ({} UTC)\nSort order: {}\n\n{}\n\nTotal BTC: {}\n".format(
		make_timestr(), " ".join(sort_info), "\n".join(pout), total
	)


def sort_and_view(unspent,opts):

	def s_amt(i):   return i.amount
	def s_txid(i):  return "%s %03s" % (i.txid,i.vout)
	def s_addr(i):  return i.address
	def s_age(i):   return i.confirmations
	def s_mmgen(i):
		m = parse_mmgen_label(i.account)[0]
		if m: return "{}:{:>0{w}}".format(w=g.mmgen_idx_max_digits, *m.split(":"))
		else: return "G" + i.account

	sort,group,show_days,show_mmaddr,reverse = "age",False,False,True,True
	unspent.sort(key=s_age,reverse=reverse) # Reverse age sort by default

	total = trim_exponent(sum([i.amount for i in unspent]))
	max_acct_len = max([len(i.account) for i in unspent])

	hdr_fmt   = "UNSPENT OUTPUTS (sort order: %s)  Total BTC: %s"
	options_msg = """
Sort options: [t]xid, [a]mount, a[d]dress, [A]ge, [r]everse, [M]mgen addr
Display options: show [D]ays, [g]roup, show [m]mgen addr, r[e]draw screen
""".strip()
	prompt = \
"('q' = quit sorting, 'p' = print to file, 'v' = pager view, 'w' = wide view): "

	from copy import deepcopy
	from mmgen.term import get_terminal_size

	write_to_file_msg = ""
	msg("")

	while True:
		cols = get_terminal_size()[0]
		if cols < g.min_screen_width:
			msg("%s-txcreate requires a screen at least %s characters wide" %
					(g.proj_name.lower(),g.min_screen_width))
			sys.exit(2)

		addr_w = min(34+((1+max_acct_len) if show_mmaddr else 0),cols-46)
		acct_w   = min(max_acct_len, max(24,int(addr_w-10)))
		btaddr_w = addr_w - acct_w - 1
		tx_w = max(11,min(64, cols-addr_w-32))
		txdots = "..." if tx_w < 64 else ""
		fs = " %-4s %-" + str(tx_w) + "s %-2s %-" + str(addr_w) + "s %-13s %-s"
		table_hdr = fs % ("Num","TX id  Vout","","Address","Amount (BTC)",
							"Age(d)" if show_days else "Conf.")

		unsp = deepcopy(unspent)
		for i in unsp: i.skip = ""
		if group and (sort == "address" or sort == "txid"):
			for a,b in [(unsp[i],unsp[i+1]) for i in range(len(unsp)-1)]:
				if sort == "address" and a.address == b.address: b.skip = "addr"
				elif sort == "txid" and a.txid == b.txid:        b.skip = "txid"

		for i in unsp:
			amt = str(trim_exponent(i.amount))
			lfill = 3 - len(amt.split(".")[0]) if "." in amt else 3 - len(amt)
			i.amt = " "*lfill + amt
			i.days = int(i.confirmations * g.mins_per_block / (60*24))
			i.age = i.days if show_days else i.confirmations
			i.mmid,i.label = parse_mmgen_label(i.account)

			if i.skip == "addr":
				i.addr = "|" + "." * 33
			else:
				if show_mmaddr:
					dots = ".." if btaddr_w < len(i.address) else ""
					i.addr = "%s%s %s" % (
						i.address[:btaddr_w-len(dots)],
						dots,
						i.account[:acct_w])
				else:
					i.addr = i.address

			i.tx = " " * (tx_w-4) + "|..." if i.skip == "txid" \
					else i.txid[:tx_w-len(txdots)]+txdots

		sort_info = ["reverse"] if reverse else []
		sort_info.append(sort if sort else "unsorted")
		if group and (sort == "address" or sort == "txid"):
			sort_info.append("grouped")

		out  = [hdr_fmt % (" ".join(sort_info), total), table_hdr]
		out += [fs % (str(n+1)+")",i.tx,i.vout,i.addr,i.amt,i.age)
					for n,i in enumerate(unsp)]

		msg("\n".join(out) +"\n\n" + write_to_file_msg + options_msg)
		write_to_file_msg = ""

		skip_prompt = False

		while True:
			reply = get_char(prompt, immed_chars="atDdAMrgmeqpvw")

			if   reply == 'a': unspent.sort(key=s_amt);  sort = "amount"
			elif reply == 't': unspent.sort(key=s_txid); sort = "txid"
			elif reply == 'D': show_days = not show_days
			elif reply == 'd': unspent.sort(key=s_addr); sort = "address"
			elif reply == 'A': unspent.sort(key=s_age);  sort = "age"
			elif reply == 'M':
				unspent.sort(key=s_mmgen); sort = "mmgen"
				show_mmaddr = True
			elif reply == 'r':
				unspent.reverse()
				reverse = not reverse
			elif reply == 'g': group = not group
			elif reply == 'm': show_mmaddr = not show_mmaddr
			elif reply == 'e': pass
			elif reply == 'q': pass
			elif reply == 'p':
				d = format_unspent_outputs_for_printing(unsp,sort_info,total)
				of = "listunspent[%s].out" % ",".join(sort_info)
				write_to_file(of, d, opts,"",False,False)
				write_to_file_msg = "Data written to '%s'\n\n" % of
			elif reply == 'v':
				do_pager("\n".join(out))
				continue
			elif reply == 'w':
				data = format_unspent_outputs_for_printing(unsp,sort_info,total)
				do_pager(data)
				continue
			else:
				msg("\nInvalid input")
				continue

			break

		msg("\n")
		if reply == 'q': break

	return tuple(unspent)


def select_outputs(unspent,prompt):

	while True:
		reply = my_raw_input(prompt).strip()

		if not reply: continue

		selected = parse_addr_idxs(reply,sep=None)

		if not selected: continue

		if selected[-1] > len(unspent):
			msg("Inputs must be less than %s" % len(unspent))
			continue

		return selected


def get_acct_data_from_wallet(c,acct_data):
	# acct_data is global object initialized by caller
	vmsg_r("Getting account data from wallet...")
	accts,i = c.listaccounts(minconf=0,includeWatchonly=True),0
	for acct in accts:
		ma,comment = parse_mmgen_label(acct)
		if ma:
			i += 1
			addrlist = c.getaddressesbyaccount(acct)
			if len(addrlist) != 1:
				msg(wmsg['too_many_acct_addresses'] % acct)
				sys.exit(2)
			seed_id,idx = ma.split(":")
			if seed_id not in acct_data:
				acct_data[seed_id] = {}
			acct_data[seed_id][idx] = (addrlist[0],comment)
	vmsg("%s %s addresses found, %s accounts total" % (i,g.proj_name,len(accts)))

def mmaddr2btcaddr_unspent(unspent,mmaddr):
	vmsg_r("Searching for {g.proj_name} address {m} in wallet...".format(g=g,m=mmaddr))
	m = [u for u in unspent if u.account.split()[0] == mmaddr]
	if len(m) == 0:
		vmsg("not found")
		return "",""
	elif len(m) > 1:
		msg(wmsg['too_many_acct_addresses'] % acct); sys.exit(2)
	else:
		vmsg("success (%s)" % m[0].address)
		return m[0].address, split2(m[0].account)[1]
	sys.exit()


def mmaddr2btcaddr(c,mmaddr,acct_data,addr_data,b2m_map):
	# assume mmaddr has already been checked
	if not acct_data: get_acct_data_from_wallet(c,acct_data)
	btcaddr,comment = mmaddr2btcaddr_addrdata(mmaddr,acct_data,"wallet")
#	btcaddr,comment = mmaddr2btcaddr_unspent(us,mmaddr)
	if not btcaddr:
		if addr_data:
			btcaddr,comment = mmaddr2btcaddr_addrdata(mmaddr,addr_data,"addr file")
			if btcaddr:
				msg(wmsg['addr_in_addrfile_only'].format(mmgenaddr=mmaddr))
				if not keypress_confirm("Continue anyway?"):
					sys.exit(1)
			else:
				msg(wmsg['addr_not_found'].format(mmgenaddr=mmaddr))
				sys.exit(2)
		else:
			msg(wmsg['addr_not_found_no_addrfile'].format(mmgenaddr=mmaddr))
			sys.exit(2)

	b2m_map[btcaddr] = mmaddr,comment
	return btcaddr


opts,cmd_args = parse_opts(sys.argv,help_data)

if g.debug: show_opts_and_cmd_args(opts,cmd_args)

if 'comment_file' in opts:
	comment = get_tx_comment_from_file(opts['comment_file'])

c = connect_to_bitcoind()

if not 'info' in opts:
	do_license_msg(immed=True)

	tx_out,addr_data,b2m_map,acct_data,change_addr = {},{},{},{},""

	addrfiles = [a for a in cmd_args if get_extension(a) == g.addrfile_ext]
	cmd_args = set(cmd_args) - set(addrfiles)

	for a in addrfiles:
		check_infile(a)
		parse_addrfile(a,addr_data)

	for a in cmd_args:
		if "," in a:
			a1,a2 = split2(a,",")
			if is_btc_addr(a1):
				btcaddr = a1
			elif is_mmgen_addr(a1):
				btcaddr = mmaddr2btcaddr(c,a1,acct_data,addr_data,b2m_map)
			else:
				msg("%s: unrecognized subargument in argument '%s'" % (a1,a))
				sys.exit(2)

			if is_btc_amt(a2):
				tx_out[btcaddr] = normalize_btc_amt(a2)
			else:
				msg("%s: invalid amount in argument '%s'" % (a2,a))
				sys.exit(2)
		elif is_mmgen_addr(a) or is_btc_addr(a):
			if change_addr:
				msg("ERROR: More than one change address specified: %s, %s" %
						(change_addr, a))
				sys.exit(2)
			change_addr = a if is_btc_addr(a) else \
				mmaddr2btcaddr(c,a,acct_data,addr_data,b2m_map)
			tx_out[change_addr] = 0
		else:
			msg("%s: unrecognized argument" % a)
			sys.exit(2)

	if not tx_out:
		msg("At least one output must be specified on the command line")
		sys.exit(2)

	tx_fee = opts['tx_fee'] if 'tx_fee' in opts else g.tx_fee
	tx_fee = normalize_btc_amt(tx_fee)
	if tx_fee > g.max_tx_fee:
		msg("Transaction fee too large: %s > %s" % (tx_fee,g.max_tx_fee))
		sys.exit(2)

if g.debug: show_opts_and_cmd_args(opts,cmd_args)

if g.bogus_wallet_data:  # for debugging purposes only
	us = eval(get_data_from_file(g.bogus_wallet_data))
else:
	us = c.listunspent()
#	write_to_file("bogus_unspent.json", repr(us), opts); sys.exit()

if not us: msg(wmsg['no_spendable_outputs']); sys.exit(2)

unspent = sort_and_view(us,opts)

total = trim_exponent(sum([i.amount for i in unspent]))

msg("Total unspent: %s BTC (%s outputs)" % (total, len(unspent)))
if 'info' in opts: sys.exit(0)

send_amt = sum([tx_out[i] for i in tx_out.keys()])
msg("Total amount to spend: %s%s" % (
		(send_amt or "Unknown")," BTC" if send_amt else ""))

while True:
	sel_nums = select_outputs(unspent,
			"Enter a range or space-separated list of outputs to spend: ")
	msg("Selected output%s: %s" %
		(("" if len(sel_nums) == 1 else "s"), " ".join(str(i) for i in sel_nums))
	)
	sel_unspent = [unspent[i-1] for i in sel_nums]

	mmaddrs = set([parse_mmgen_label(i.account)[0] for i in sel_unspent])
	mmaddrs.discard("")

	if mmaddrs and len(mmaddrs) < len(sel_unspent):
		msg(wmsg['mixed_inputs'] % ", ".join(sorted(mmaddrs)))
		if not keypress_confirm("Accept?"):
			continue

	total_in = trim_exponent(sum([i.amount for i in sel_unspent]))
	change   = trim_exponent(total_in - (send_amt + tx_fee))

	if change >= 0:
		prompt = "Transaction produces %s BTC in change.  OK?" % change
		if keypress_confirm(prompt,default_yes=True):
			break
	else:
		msg(wmsg['not_enough_btc'] % change)

if change > 0 and not change_addr:
	msg(wmsg['throwaway_change'] % change)
	sys.exit(2)

if change_addr in tx_out and not change:
	msg("Warning: Change address will be unused as transaction produces no change")
	del tx_out[change_addr]

for k,v in tx_out.items(): tx_out[k] = float(v)

if change > 0: tx_out[change_addr] = float(change)

tx_in = [{"txid":i.txid, "vout":i.vout} for i in sel_unspent]

if g.debug:
	print "tx_in:", repr(tx_in)
	print "tx_out:", repr(tx_out)

if 'comment_file' in opts:
	if keypress_confirm("Edit comment?",False):
		comment = get_tx_comment_from_user(comment)
else:
	if keypress_confirm("Add a comment to transaction?",False):
		comment = get_tx_comment_from_user()
	else: comment = False

tx_hex = c.createrawtransaction(tx_in,tx_out)
qmsg("Transaction successfully created")

amt = send_amt or change
tx_id = make_chksum_6(unhexlify(tx_hex)).upper()
metadata = tx_id, amt, make_timestamp()

prompt_and_view_tx_data(c,"View decoded transaction?",
	[i.__dict__ for i in sel_unspent],tx_hex,b2m_map,comment,metadata)

prompt = "Save transaction?"
if keypress_confirm(prompt,default_yes=True):
	outfile = "tx_%s[%s].%s" % (tx_id,amt,g.rawtx_ext)
	data = make_tx_data("{} {} {}".format(*metadata), tx_hex,
			[i.__dict__ for i in sel_unspent], b2m_map, comment)
	write_to_file(outfile,data,opts,"transaction",False,True)
else:
	msg("Transaction not saved")
