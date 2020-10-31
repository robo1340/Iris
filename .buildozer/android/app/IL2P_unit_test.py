import numpy as np

from IL2P import IL2P_Frame_Header, IL2P_Frame_Engine
import exceptions
from fec.fec import inject_symbol_errors

########header packing/unpacking unit test ##################
header_obj = IL2P_Frame_Header(src_callsign='BAYWAX',dst_callsign='WAYGAK',src_ssid=0x0f,dst_ssid=0x03,ui=1,pid=2,control=0x74,header_type=3,payload_byte_count=1023)
header_bytes = header_obj.pack_header()
header_obj2 = IL2P_Frame_Header.unpack_header(header_bytes)

if (header_obj.equals(header_obj2)):
	print('The headers match after packing/unpacking')
else:
	print('FAILURE: at least one of the header field(s) do not match after packing/unpacking')


########### full IL2P unit test #########################

frame_engine = IL2P_Frame_Engine()
msg_str = 'What the fuck did you just fucking say about me, you little bitch? Ill have you know I graduated top of my class in the Navy Seals, and Ive been involved in numerous secret raids on Al-Quaeda, and I have over 300 confirmed kills.'
header = IL2P_Frame_Header(src_callsign='BAYWAX',dst_callsign='WAYGAK',header_type=3,payload_byte_count=len(msg_str))

frame_to_send = frame_engine.encode_frame(header, np.frombuffer(msg_str.encode(),dtype=np.uint8))
corrupted_frame = inject_symbol_errors(frame_to_send, 0.95)

try:
	(header_received, decode_success, payload_received) = frame_engine.decode_frame(frame_to_send)
except exceptions.IL2PHeaderDecodeError:
	print('FAILURE: header could not be decoded')

if not(header.equals(header_received)):
	print('FAILURE: headers do not match')
print(payload_received.tobytes().decode())

###############################################

frame_engine = IL2P_Frame_Engine()
msg_str = 'message'
header = IL2P_Frame_Header(src_callsign='BAYWAX',dst_callsign='WAYGAK',header_type=3,payload_byte_count=len(msg_str))

frame_to_send = frame_engine.encode_frame(header, np.frombuffer(msg_str.encode(),dtype=np.uint8))
corrupted_frame = inject_symbol_errors(frame_to_send, 0.95)

try:
	(header_received, decode_success, payload_received) = frame_engine.decode_frame(frame_to_send)
except exceptions.IL2PHeaderDecodeError:
	print('FAILURE: header could not be decoded')

if not(header.equals(header_received)):
	print('FAILURE: headers do not match')
print(payload_received.tobytes().decode())

###############################################

msg = np.zeros((1023),dtype=np.uint8)
for i in range(0,msg.size):
	msg[i] = np.uint8(i)

header.setPayloadSize(msg.size)
frame_to_send = frame_engine.encode_frame(header, msg)
corrupted_frame = inject_symbol_errors(frame_to_send, 0.95)


try:
	(header_received, decode_success, payload_received) = frame_engine.decode_frame(frame_to_send)
except exceptions.IL2PHeaderDecodeError:
	print('FAILURE: header could not be decoded')

if not(header.equals(header_received)):
	print('FAILURE: headers do not match')
print(payload_received)

