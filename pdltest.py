#!/usr/bin/env python3

import enum
import struct
import sys
import time

import serial
#import usb1

PDL_TAG = b'\xae'

HOST_PACKET_FLOWID = b'\xff'
FLOWID_DATA        = b'\xbb'
FLOWID_ACK         = b'\xff'
FLOWID_ERROR       = b'\xee'

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
		_communicate(sport, Commands.CONNECT)
#		_communicate(sport, Commands.START_DATA, _pack32(0x100100) + _pack32(0x7f80))

def _pack32(num):
	return struct.pack('<I', num)

def _communicate(interface, cmd, payload=b''):
	_send_command(interface, cmd, payload)
	return _receive_command(interface)

def _send_command(interface, cmd, payload=b''):
	if cmd in Commands.__members__.values():
		cmdnum = cmd.value
	else:
		print("Command %r not in commands" % (cmd,))
		sys.exit(2)

	print("<- %s" % (cmd,))
	data = struct.pack('<I', cmdnum) + payload
	_send_packet(interface, data)

def _receive_command(interface):
	(data, flowid) = _receive_packet(interface)
	rspdata = data[0:4]
	(rsp,) = struct.unpack('<I', rspdata)

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

#	with usb1.USBContext() as context:
#		try:
#			handle = context.openByVendorIDAndProductID(0x0525, 0xa4a7)
#		except usb1.USBErrorAccess as e:
#			print(e)
#			sys.exit(2)

#		print("Opened %s" % (handle.getDevice(),))

#		with handle.claimInterface(1) as interface:
#			print(dir(interface))
#			handle.bulkWrite(bytes.fromhex('ae 04 00 00 00 ff 00 00 00 00'))
#			handle.bulkWrite(bytes.fromhex('ae 0c 00 00 00 ff 04 00 00 00 00 01 10 00 80 7f 00 00'))
#			handle.bulkRead
#			print(dir(handle))

if __name__ == '__main__':
	main()
