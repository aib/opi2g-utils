#!/usr/bin/env python3
"""Reads/extracts a firmware image as used by the OrangePi NAND Update Tool"""

import binascii
import os.path
import struct
import sys

def read_bin(bin_filename, export_dir=None):
	with open(bin_filename, 'rb') as f:
		r = _reader(f, '<')
		sections = []

		no_of_sections = r('I')

		for i in range(no_of_sections):
			offset = r('I')
			length = r('I')
			u1 = r('I')
			u2 = r('I')
			label1 = r('128s').decode('ascii').rstrip('\0')
			label2 = r('128s').decode('ascii').rstrip('\0')
			full_filename = r('1024s').decode('ascii').rstrip('\0')
			filename = full_filename.split('\\')[-1]
			flag1 = r('I')
			flag2 = r('I')

			section = (i, offset, length, u1, u2, label1, label2, full_filename, filename, flag1, flag2)
			sections.append(section)

		data = f.read()

		header_length = 4 + 1304 * no_of_sections
		data_length = sum(map(lambda s: s[2], sections))
		actual_data_length = len(data)
		total_length = header_length + data_length
		actual_total_length = header_length + actual_data_length
		file_size = os.path.getsize(bin_filename)

		print("Sections:                 %8d" % (no_of_sections,))
		print("Header length:            %08x (%d)" % (header_length, header_length))
		print("Data length (calculated): %08x (%d)" % (data_length, data_length))
		print("Data length (actual):     %08x (%d)" % (actual_data_length, actual_data_length))
		print("Total (calculated):       %08x (%d)" % (total_length, total_length))
		print("Total (actual):           %08x (%d)" % (actual_total_length, actual_total_length))
		print("File size:                %08x (%d)" % (file_size, file_size))
		print("")

		for section in sections:
			(i, offset, length, u1, u2, label1, label2, full_filename, filename, flag1, flag2) = section
			section_data = data[offset:offset+length]

			print("Section %d: %s %s (%s)" % (i+1, label1, label2, full_filename))
			print("  - Offset:   %08x" % (offset,))
			print("  - Length:   %08x (%d)" % (length, length))
			print("  - Unknown1: %08x" % (u1,))
			print("  - Unknown2: %08x" % (u2,))
			print("  - Ends:     %08x" % (offset + length,))
			print("  - Flag1:    %8d" % (flag1,))
			print("  - Flag2:    %8d" % (flag2,))
			print("")

			if export_dir is not None:
				target_filename = os.path.join(export_dir, filename)
				print("* Written to %s" % (target_filename,))
				print("")
				with open(target_filename, 'wb') as df:
					df.write(section_data)

def main():
	if len(sys.argv) < 2:
		print("Usage:\n\t%s <BIN> [export_dir]\n" % (sys.argv[0],))
		sys.exit(1)

	filename = sys.argv[1]
	print("%s:" % (filename,))
	print("")

	read_bin(filename, sys.argv[2] if len(sys.argv) > 2 else None)

def _reader(f, byte_order):
	def _unpacker(fmt_):
		fmt = byte_order + fmt_
		b = f.read(struct.calcsize(fmt))
		val = struct.unpack(fmt, b)
		if len(val) == 1:
			return val[0]
		else:
			return val
	return _unpacker

if __name__ == '__main__':
	main()
