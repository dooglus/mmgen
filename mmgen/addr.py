#!/usr/bin/env python
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C) 2013 by philemon <mmgen-py@yandex.com>
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
addr.py:  Address generation/display routines for mmgen suite
"""

import sys
from hashlib import sha256, sha512
from binascii import hexlify, unhexlify

from mmgen.bitcoin import numtowif

def test_for_keyconv():
	"""
	Test for the presence of 'keyconv' utility on system
	"""

	keyconv_exec = "keyconv"

	from subprocess import Popen, PIPE
	try:
		p = Popen([keyconv_exec, '-h'], stdout=PIPE, stderr=PIPE)
	except:
		sys.stderr.write("""
Executable '%s' unavailable.  Falling back on (slow) internal ECDSA library.
Please install '%s' from the %s package on your system for much faster
address generation.

""" % (keyconv_exec, keyconv_exec, "vanitygen"))
		return False
	else:
		return True


def generate_addrs(seed, start, end, opts):
	"""
	generate_addresses(start, end, seed, opts)  => None

	Generate a series of Bitcoin addresses from start to end based on a
	seed, optionally outputting secret keys

	The 'keyconv' utility will be used for address generation if
	installed.  Otherwise an internal function is used

	Supported options:
	  print_secret, no_addresses, no_keyconv, gen_what
	
	Addresses are returned in a list of dictionaries with the following keys:
	  num, sec, wif, addr
	"""

	if not 'no_addresses' in opts:
		if 'no_keyconv' in opts or test_for_keyconv() == False:
			sys.stderr.write("Using (slow) internal ECDSA library for address generation\n")
			from mmgen.bitcoin import privnum2addr
			keyconv = ""
		else:
			from subprocess import Popen, PIPE
			keyconv = "keyconv"

	total_addrs = end - start + 1

	addrlist = []

	for i in range(1, end+1):
		seed = sha512(seed).digest() # round /i/

		if i < start: continue

		sys.stderr.write("\rGenerating %s: %s of %s" %
			(opts['gen_what'], (i-start)+1, total_addrs))

		# Secret key is double sha256 of seed hash round /i/
		sec = sha256(sha256(seed).digest()).hexdigest()
		wif = numtowif(int(sec,16))

		el = { 'num': i }

		if not 'print_addresses_only' in opts:
			el['sec'] = sec
			el['wif'] = wif

		if not 'no_addresses' in opts:
			if keyconv:
				p = Popen([keyconv, wif], stdout=PIPE)
				addr = dict([j.split() for j in p.stdout.readlines()])['Address:']
			else:
				addr = privnum2addr(int(sec,16))

			el['addr'] = addr

		addrlist.append(el)

	sys.stderr.write("\rGenerated %s %s-%s%s\n" %
		(opts['gen_what'], start, end, " "*9))

	return addrlist


def format_addr_data(addrlist, seed_chksum, opts):
	"""
	print_addresses(addrs, opts)  => None

	Print out the addresses and/or keys generated by generate_addresses()

	By default, prints addresses only

	Output can be customized with the following command line options:
	  print_secret
	  no_addresses
	  b16
	"""

	start = addrlist[0]['num']
	end   = addrlist[-1]['num']

	wif_msg = ""
	if ('b16' in opts and 'print_secret' in opts) \
		or 'no_addresses' in opts:
			wif_msg = " (wif)"

	fa = "%s%%-%ss %%-%ss %%s" % (
			" "*2, len(str(end)) + (0 if 'no_addresses' in opts else 1),
			(5 if 'print_secret' in opts else 1) + len(wif_msg)
		)

	data = []
	data.append("%s {" % seed_chksum.upper())

	for el in addrlist:
		col1 = el['num']
		if 'no_addresses' in opts:
			if 'b16' in opts:
				data.append(fa % (col1, " (hex):", el['sec']))
				col1 = ""
			data.append(fa % (col1, " (wif):", el['wif']))
			if 'b16' in opts: data.append("")
		elif 'print_secret' in opts:
			if 'b16' in opts:
				data.append(fa % (col1, "sec (hex):", el['sec']))
				col1 = ""
			data.append(fa % (col1, "sec"+wif_msg+":", el['wif']))
			data.append(fa % ("",   "addr:", el['addr']))
			data.append("")
		else:
			data.append(fa % (col1, "", el['addr']))

	if not data[-1]: data.pop()
	data.append("}")

	return "\n".join(data) + "\n"


def write_addr_data_to_file(seed, data, start, end, opts):

	if 'print_addresses_only' in opts: ext = "addrs"
	elif 'no_addresses' in opts:       ext = "keys"
	else:                              ext = "akeys"

	if 'b16' in opts: ext = ext.replace("keys","xkeys")

	from mmgen.utils import write_to_file, make_chksum_8, msg
	addr_range = str(start) if start == end else "%s-%s" % (start,end)
	outfile = "{}[{}].{}".format(make_chksum_8(seed),addr_range,ext)
	if 'outdir' in opts:
		outfile = "%s/%s" % (opts['outdir'], outfile)

#	print outfile; sys.exit(3)
	write_to_file(outfile,data)

	dtype = "Address" if 'print_addresses_only' in opts else "Key"
	msg("%s data saved to file '%s'" % (dtype,outfile))