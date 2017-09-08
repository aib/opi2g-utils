#!/usr/bin/env python3

import argparse
import binascii
import enum
import struct
import sys
import time

import serial

g_config = {
	'print_chunks': False,
	'print_commands': False
}

PDL_TAG = b'\xae'

HOST_PACKET_FLOWID = b'\xff'
FLOWID_DATA        = b'\xbb'
FLOWID_ACK         = b'\xff'
FLOWID_ERROR       = b'\xee'

CONFIG_MTD_PTBL_OFFS = 49152
MAX_PART_NAME = 30

class Commands(enum.Enum):
	CONNECT = 0
	ERASE_FLASH = 1
	ERASE_PARTITION = 2
	ERASE_ALL = 3
	START_DATA = 4
	MID_DATA = 5
	END_DATA = 6
	EXEC_DATA = 7
	READ_FLASH = 8
	READ_PARTITION = 9
	NORMAL_RESET = 10
	READ_CHIPID = 11
	SET_BAUDRATE = 12
	FORMAT_FLASH = 13
	READ_PARTITION_TABLE = 14
	READ_IMAGE_ATTR = 15
	GET_VERSION = 16
	SET_FACTMODE = 17
	SET_CALIBMODE = 18
	SET_PDL_DBG = 19
	CHECK_PARTITION_TABLE = 20
	POWER_OFF = 21
	IMAGE_LIST = 22
	GET_SWCFG_REG = 23
	SET_SWCFG_REG = 24
	GET_HWCFG_REG = 25
	SET_HWCFG_REG = 26
	EXIT_AND_RELOAD = 27
	GET_SECURITY = 28
	HW_TEST = 29
	GET_PDL_LOG = 30
	DOWNLOAD_FINISH = 31

class Responses(enum.Enum):
	ACK = 0
	#from PC command
	PACKET_ERROR = 1
	INVALID_CMD = 2
	UNKNOWN_CMD = 3
	INVALID_ADDR = 4
	INVALID_BAUDRATE = 5
	INVALID_PARTITION = 6
	INVALID_SIZE = 7
	WAIT_TIMEOUT = 8
	#from phone
	VERIFY_ERROR = 9
	CHECKSUM_ERROR = 10
	OPERATION_FAILED = 11
	#phone internal
	DEVICE_ERROR = 12 #DDR,NAND init errors
	NO_MEMORY = 13
	DEVICE_INCOMPATIBLE = 14
	HW_TEST_ERROR = 15
	MD5_ERROR = 16
	ACK_AGAIN_ERASE = 17
	ACK_AGAIN_FLASH = 18
	MAX_RSP = 19

def main():
	example = "%s bootloader:bootloader.bin root:/tmp/ubi.img" % (sys.argv[0],)
	argparser = argparse.ArgumentParser(epilog="Example:\n\t%s\n " % (example,), formatter_class=argparse.RawDescriptionHelpFormatter)

	argparser.add_argument(
		'-p', '--port',
		help="Serial port to use",
		default='/dev/ttyACM0'
	)

	argparser.add_argument(
		'--pdl1',
		help="PDL1 binary file to use",
		default='pdl1.bin'
	)

	argparser.add_argument(
		'--pdl2',
		help="PDL2 binary file to use",
		default='pdl2.bin'
	)

	argparser.add_argument(
		'--skippdl', '--skip-pdl',
		help="Skip uploading and executing the PDL1 and PDL2 stages",
		action='store_true'
	)

	argparser.add_argument(
		'--format-flash',
		help="Format the entire memory prior to uploading the partitions",
		action='store_true'
	)

	argparser.add_argument(
		'partition',
		help="<partition_name>:<image_file> pair to upload",
		nargs='*'
	)

	argparser.add_argument(
		'-v', '--verbose',
		help="Increase verbosity (repeat for more)",
		action='count',
		default=0
	)

	args = argparser.parse_args()

	pp = []
	for p in args.partition:
		try:
			(pname, pfile) = p.split(':')
			pp.append((pname, pfile))
		except ValueError:
			print("Cannot parse partition spec \"%s\"" % (p,))
			sys.exit(1)
	args.partitions_parsed = pp

	if args.verbose >= 1:
		g_config['print_chunks'] = True

	if args.verbose >= 2:
		g_config['print_commands'] = True

	_do_upload(args)

	print("Done")

def _do_upload(args):
	print("Opening %s..." % (args.port,))
	with serial.Serial(args.port, 115200) as sport:
		if not args.skippdl:
			_do_pdls(sport, args.pdl1, args.pdl2)

		_print_partition_table(sport)

		if args.format_flash:
			print("Formatting flash memory...")
			_communicate(sport, Commands.FORMAT_FLASH)
			_print_partition_table(sport)

		if len(args.partitions_parsed) > 0:
			_upload_partitions(sport, args.partitions_parsed)

def _do_pdls(interface, pdl1path, pdl2path):
	_communicate(interface, Commands.CONNECT)
	with open(pdl1path, 'rb') as f:
		_send_partition_data(interface, "pdl1", f.read(), 0x00100100, chunk_size=4096)
	_communicate(interface, Commands.EXEC_DATA, _pack32(0x00100100))

	_communicate(interface, Commands.CONNECT)
	with open(pdl2path, 'rb') as f:
		_send_partition_data(interface, "pdl2", f.read(), 0x80008000, chunk_size=4096)
	_communicate(interface, Commands.EXEC_DATA, _pack32(0x80008000))

def _upload_partitions(interface, partitions):
	_communicate(interface, Commands.CONNECT)

	image_list = ','.join(list(map(lambda p: p[0], partitions))).encode('ascii')
	crc = binascii.crc32(image_list)
	_communicate(interface, Commands.IMAGE_LIST, _pack32(0) + _pack32(crc) + image_list)

	for (pname, pfile) in partitions:
		with open(pfile, 'rb') as f:
			data = f.read()
			_send_partition_data(interface, pname, data, chunk_size=256*1024)

	_communicate(interface, Commands.DOWNLOAD_FINISH)

def _print_partition_table(interface):
	partition_table = _communicate(interface, Commands.READ_PARTITION_TABLE, raw_response=True).decode('ascii')
	print("Partition table: %s" % (partition_table,))

def _send_partition_data(interface, partname, data, target_addr=0, chunk_size=4096):
	print("Sending partition %s (len %d) to 0x%08x" % (partname, len(data), target_addr))

	pname = partname.encode('ascii')
	pname += b'\0' * (MAX_PART_NAME - len(pname))

	_communicate(interface, Commands.START_DATA, _pack32(target_addr) + _pack32(len(data)) + pname)
	total = 0
	for (f, chunk) in enumerate(_chunk_data(data, chunk_size)):
		total += len(chunk)
		if g_config['print_chunks']:
			print("Sent chunk %d, size %d, total %d (%x)" % (f, len(chunk), total, total))
		_communicate(interface, Commands.MID_DATA, _pack32(f) + _pack32(len(chunk)) + chunk)

	crc = binascii.crc32(data)
	_communicate(interface, Commands.END_DATA, _pack32(0) + _pack32(4) + _pack32(crc))

def _chunk_data(data, chunk_size):
	chunks = []
	off = 0
	while off < len(data):
		chunk = data[off:off+chunk_size]
		chunks.append(chunk)
		off += len(chunk)
	return chunks

def _pack32(num):
	return struct.pack('<I', num)

def _communicate(interface, cmd, payload=b'', raw_response=False):
	_send_command(interface, cmd, payload)
	return _receive_command(interface, raw_response)

def _send_command(interface, cmd, payload=b''):
	if cmd in Commands.__members__.values():
		cmdnum = cmd.value
	else:
		print("Command %r not in commands" % (cmd,))
		sys.exit(2)

	if g_config['print_commands']:
		print("<- %s" % (cmd,))
	data = struct.pack('<I', cmdnum) + payload
	_send_packet(interface, data)

def _receive_command(interface, raw_response=False):
	(data, flowid) = _receive_packet(interface)
	rspdata = data[0:4]
	(rsp,) = struct.unpack('<I', rspdata)

	if raw_response:
		if g_config['print_commands']:
			print("-> (RAW) %r" % (data,))
		return data
	else:
		for (key, e) in Responses.__members__.items():
			if rsp == e.value:
				if g_config['print_commands']:
					print("-> %s" % (e,))
				return e

		print("Response %r not in responses" % (rspdata,))

def _send_packet(interface, data):
	pkt = PDL_TAG + struct.pack('<I', len(data)) + HOST_PACKET_FLOWID + data
	interface.write(pkt)

def _receive_packet(interface):
	tag = interface.read(1)

	if tag != PDL_TAG:
		print("Invalid tag %r" % (tag,))
		sys.exit(2)

	(size,) = struct.unpack('<I', interface.read(4))
	flowid = interface.read(1)
	data = interface.read(size)

	if flowid == FLOWID_ERROR:
		(errcode,) = struct.unpack('<I', data)
		for (key, e) in Responses.__members__.items():
			if errcode == e.value:
				print("Error: %s" % (e,))
				sys.exit(2)

		print("Unknown error: %r" % (data,))
		sys.exit(2)

	if flowid not in [FLOWID_ACK, FLOWID_DATA]:
		print("Invalid flowid: %r" % (flowid,))
		sys.exit(2)

	return (data, flowid)

if __name__ == '__main__':
	main()
