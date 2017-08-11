#!/usr/bin/env python3

import enum
import struct
import sys
import time

import serial

PDL_TAG = b'\xae'

HOST_PACKET_FLOWID = b'\xff'
FLOWID_DATA        = b'\xbb'
FLOWID_ACK         = b'\xff'
FLOWID_ERROR       = b'\xee'

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
	with serial.Serial('/dev/ttyACM0', 115200) as sport:
		if not 'skippdl' in sys.argv:
			_do_pdls(sport)
		_upload_partitions(sport)

def _do_pdls(interface):
	_communicate(interface, Commands.CONNECT)
	_send_file(interface, "/tmp/rom/pdl1.bin", 0x00100100, 4096)
	_communicate(interface, Commands.EXEC_DATA, _pack32(0x00100100))

	_communicate(interface, Commands.CONNECT)
	_send_file(interface, "/tmp/rom/pdl2.bin", 0x80008000, 4096)
	_communicate(interface, Commands.EXEC_DATA, _pack32(0x80008000))

def _upload_partitions(interface):
		_communicate(interface, Commands.IMAGE_LIST, _pack32(0) + _pack32(0x65646568) + "bootloader,nandroot".encode('ascii'))
		_send_partition(interface, "hodo", "/home/aib/proj/opi/git/u-boot/u-boot-nand.rda", 0x00000000)
		_send_partition(interface, "nandroot", "/home/aib/proj/opi/mtd3/mtd1.bak", 0x00200000)

def _send_partition(interface, partname, filename, target_addr, chunk_size=4096):
	print("Sending file %s as partition %s to 0x%08x" % (filename, partname, target_addr))

	(chunks, total_size) = _get_file_chunks(filename, chunk_size)

	pname = partname.encode('ascii')
	pname += b'\0' * (MAX_PART_NAME - len(pname))

	_communicate(interface, Commands.START_DATA, _pack32(target_addr) + _pack32(total_size) + pname)
	for (f, chunk) in enumerate(chunks):
		_communicate(interface, Commands.MID_DATA, _pack32(f) + _pack32(len(chunk)) + chunk)
	_communicate(interface, Commands.END_DATA)

def _send_file(interface, filename, target_addr, chunk_size=4096):
	print("Sending file %s to 0x%08x" % (filename, target_addr))

	(chunks, total_size) = _get_file_chunks(filename, chunk_size)

	_communicate(interface, Commands.START_DATA, _pack32(target_addr) + _pack32(total_size))
	for chunk in chunks:
		_communicate(interface, Commands.MID_DATA, _pack32(0) + _pack32(len(chunk)) + chunk)
	_communicate(interface, Commands.END_DATA)

def _get_file_chunks(filename, chunk_size):
	chunks = []
	with open(filename, 'rb') as f:
		while True:
			chunk = f.read(chunk_size)
			if len(chunk) == 0:
				break
			chunks.append(chunk)

		total_size = sum(map(lambda c: len(c), chunks))
	return (chunks, total_size)

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

	print("<- %s" % (cmd,))
	data = struct.pack('<I', cmdnum) + payload
	_send_packet(interface, data)

def _receive_command(interface, raw_response=False):
	(data, flowid) = _receive_packet(interface)
	rspdata = data[0:4]
	(rsp,) = struct.unpack('<I', rspdata)

	if raw_response:
		return data
	else:
		for (key, e) in Responses.__members__.items():
			if rsp == e.value:
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
		print("Error: %r" % (data,))
		sys.exit(2)

	if flowid not in [FLOWID_ACK, FLOWID_DATA]:
		print("Invalid flowid: %r" % (flowid,))
		sys.exit(2)

	return (data, flowid)

if __name__ == '__main__':
	main()
