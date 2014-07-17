#!/usr/bin/env python
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C) 2013-2014 by philemon <mmgen-py@yandex.com>
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
tool.py:  Routines and data for the mmgen-tool utility
"""

import sys
import mmgen.bitcoin as bitcoin

from mmgen.util import *

commands = {
#	"keyconv_compare":          ['wif [str]'],
#	"keyconv_compare_randloop": ['iterations [int]'],
#	"hextob58_pad":             ['hexnum [str]],
#	"b58tohex_pad":             ['b58num [str]'],
#	"hextob58_pad_randloop":    ['iterations [int]'],
#	"test_wiftohex":            ['wif [str]'],
#	"hextosha256":              ['hexnum [str]'],
#	"hextowiftopubkey":         ['hexnum [str]'],
#	"pubhextoaddr":             ['hexnum [str]'],
#	"hextowif_comp":            ['hexnum [str]'],
#	"wiftohex_comp":            ['wif [str]'],
#	"privhextoaddr_comp":       ['hexnum [str]'],
#	"wiftoaddr_comp":           ['wif [str]'],
	"strtob58":     ['<string> [str]'],
	"hextob58":     ['<hex number> [str]'],
	"b58tohex":     ['<b58 number> [str]'],
	"b58randenc":   [],
	"randwif":      ['compressed [bool=False]'],
	"randpair":     ['compressed [bool=False]'],
	"wif2addr":     ['<wif> [str]', 'compressed [bool=False]'],
	"hexdump":      ['<infile> [str]', 'cols [int=8]', 'line_nums [bool=True]'],
	"unhexdump":    ['<infile> [str]'],
	"mn_rand128":   ['wordlist [str="electrum"]'],
	"mn_rand192":   ['wordlist [str="electrum"]'],
	"mn_rand256":   ['wordlist [str="electrum"]'],
	"mn_stats":     ['wordlist [str="electrum"]'],
	"mn_printlist": ['wordlist [str="electrum"]']
}

command_help = """
General operations:
hexdump      - encode binary data in formatted hexadecimal form
unhexdump    - decode formatted hexadecimal data

Bitcoin operations:
strtob58     - convert a string to base 58
hextob58     - convert a hexadecimal number to base 58
b58tohex     - convert a base 58 number to hexadecimal
b58randenc   - generate a random 32-byte number and convert it to base 58
randwif      - generate a random private key in WIF format
randpair     - generate a random private key/address pair
wif2addr     - generate a Bitcoin address from a key in WIF format

Mnemonic operations (choose "electrum" (default), "tirosh" or "all" wordlists):
mn_rand128   - generate random 128-bit mnemonic
mn_rand192   - generate random 192-bit mnemonic
mn_rand256   - generate random 256-bit mnemonic
mn_stats     - show stats for mnemonic wordlist
mn_printlist - print mnemonic wordlist

IMPORTANT NOTE: Though MMGen mnemonics use the Electrum wordlist, they're
computed using a different algorithm and are NOT Electrum-compatible!
"""

def tool_usage(prog_name, command):
	print "USAGE: '%s %s%s'" % (prog_name, command,
		(" "+" ".join(commands[command]) if commands[command] else ""))

def process_args(prog_name, command, uargs):
	cargs = commands[command]
	cargs_req = [[i.split(" [")[0],i.split(" [")[1][:-1]]
		for i in cargs if "=" not in i]
	cargs_nam = dict([[
			i.split(" [")[0],
			[i.split(" [")[1].split("=")[0], i.split(" [")[1].split("=")[1][:-1]]
		] for i in cargs if "=" in i])
	uargs_req = [i for i in uargs if "=" not in i]
	uargs_nam = dict([i.split("=") for i in uargs if "=" in i])

#	print cargs_req; print cargs_nam; print uargs_req; print uargs_nam; sys.exit()

	n = len(cargs_req)
	if len(uargs_req) != n:
		print "ERROR: %s argument%s required" % (n, " is" if n==1 else "s are")
		tool_usage(prog_name, command)
		sys.exit(1)

	for a in uargs_nam.keys():
		if a not in cargs_nam.keys():
			print "'%s' invalid named argument" % a
			sys.exit(1)

	def test_type(arg_type,arg,name=""):
		try:
			t = type(eval(arg))
			assert(t == eval(arg_type))
		except:
			print "'%s': Invalid argument for argument %s ('%s' required)" % \
				(arg, name, arg_type)
			sys.exit(1)
		return True

	ret = []

	for i in range(len(cargs_req)):
		arg,arg_type = uargs_req[i], cargs_req[i][1]
		if arg == "true" or arg == "false": arg = arg.capitalize()
		if arg_type == "str":
			ret.append('"%s"' % (arg))
		elif test_type(arg_type, arg, "#"+str(i+1)):
			ret.append('%s' % (arg))

	for k in uargs_nam.keys():
		arg,arg_type = uargs_nam[k], cargs_nam[k][0]
		if arg == "true" or arg == "false": arg = arg.capitalize()
		if arg_type == "str":
			ret.append('%s="%s"' % (k, arg))
		elif test_type(arg_type, arg, "'"+k+"'"):
			ret.append('%s=%s' % (k, arg))

	return ret


# Individual commands

def print_convert_results(indata,enc,dec,no_recode=False):
	vmsg("Input:         [%s]" % indata)
	vmsg_r("Encoded data:  ["); msg_r(enc); vmsg_r("]"); msg("")
	if not no_recode:
		vmsg("Recoded data:  [%s]" % dec)
		if indata != dec:
			msg("WARNING! Recoded number doesn't match input stringwise!")

def hexdump(infile, cols=8, line_nums=True):
	data = get_data_from_file(infile)
	o = pretty_hexdump(data, 2, cols, line_nums)
	print o

def unhexdump(infile):
	data = get_data_from_file(infile)
	o = decode_pretty_hexdump(data)
	sys.stdout.write(o)

def strtob58(s):
	enc = bitcoin.b58encode(s)
	dec = bitcoin.b58decode(enc)
	print_convert_results(s,enc,dec)

def hextob58(s,f_enc=bitcoin.b58encode, f_dec=bitcoin.b58decode):
	enc = f_enc(unhexlify(s))
	dec = hexlify(f_dec(enc))
	print_convert_results(s,enc,dec)

def b58tohex(s,f_enc=bitcoin.b58decode, f_dec=bitcoin.b58encode):
	tmp = f_enc(s)
	if tmp == False: sys.exit(1)
	enc = hexlify(tmp)
	dec = f_dec(unhexlify(enc))
	print_convert_results(s,enc,dec)

def get_random(length):
	from Crypto import Random
	return Random.new().read(length)

def b58randenc():
	r = get_random(32)
	enc = bitcoin.b58encode(r)
	dec = bitcoin.b58decode(enc)
	print_convert_results(hexlify(r),enc,hexlify(dec))

def randwif(compressed=False):
	r_hex = hexlify(get_random(32))
	enc = bitcoin.hextowif(r_hex,compressed)
	print_convert_results(r_hex,enc,"",no_recode=True)

def randpair(compressed=False):
	r_hex = hexlify(get_random(32))
	wif = bitcoin.hextowif(r_hex,compressed)
	addr = bitcoin.privnum2addr(int(r_hex,16),compressed)
	vmsg("Key (hex):  %s" % r_hex)
	vmsg_r("Key (WIF):  "); msg(wif)
	vmsg_r("Addr:       "); msg(addr)

def wif2addr(s_in,compressed=False):
	s_enc = bitcoin.wiftohex(s_in,compressed)
	if s_enc == False:
		msg("Invalid address")
		sys.exit(1)
	addr = bitcoin.privnum2addr(int(s_enc,16),compressed)
	vmsg_r("Addr: "); msg(addr)

from mmgen.mnemonic import *
from mmgen.mn_electrum  import electrum_words as el
from mmgen.mn_tirosh    import tirosh_words   as tl

wordlists = sorted(wl_checksums.keys())

def get_wordlist(wordlist):
	wordlist = wordlist.lower()
	if wordlist not in wordlists:
		msg('"%s": invalid wordlist.  Valid choices: %s' %
			(wordlist,'"'+'" "'.join(wordlists)+'"'))
		sys.exit(1)
	return el if wordlist == "electrum" else tl

def do_random_mn(nbytes,wordlist):
	r = get_random(nbytes)
	wlists = wordlists if wordlist == "all" else [wordlist]
	for wl in wlists:
		l = get_wordlist(wl)
		if wl == wlists[0]: vmsg("Seed: %s" % hexlify(r))
		mn = get_mnemonic_from_seed(r,l.strip().split("\n"),
				wordlist,print_info=False)
		vmsg("%s wordlist mnemonic:" % (wl.capitalize()))
		print " ".join(mn)

def mn_rand128(wordlist="electrum"): do_random_mn(16,wordlist)
def mn_rand192(wordlist="electrum"): do_random_mn(24,wordlist)
def mn_rand256(wordlist="electrum"): do_random_mn(32,wordlist)

def mn_stats(wordlist="electrum"):
	l = get_wordlist(wordlist)
	check_wordlist(l,wordlist)

def mn_printlist(wordlist="electrum"):
	l = get_wordlist(wordlist)
	print "%s" % l.strip()