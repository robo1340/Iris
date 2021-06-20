import numpy as np
import pickle
import IL2P
from IL2P import IL2P_Frame_Header, IL2P_Frame_Engine
import exceptions
from fec.fec import inject_symbol_errors

frame_engine = IL2P_Frame_Engine()

########header packing/unpacking unit test ##################
header_obj = IL2P_Frame_Header(src_callsign='BAYWAX', dst_callsign='WAYWAX',\
                               hops=2, is_text_msg=False, is_beacon=True, \
                               acks=[True,True,True,True], \
                               request_ack=True, request_double_ack=False, \
                               payload_size=1000, data=np.array([10,11,12,13],dtype=np.uint16))
header_bytes = header_obj.pack_header()
header_obj2 = IL2P_Frame_Header.unpack_header(header_bytes)

if (header_obj.equals(header_obj2)):
    print('The headers match after packing/unpacking')
else:
    print('FAILURE: at least one of the header field(s) do not match after packing/unpacking')
    header_obj.print_header()
    header_obj2.print_header()


########### full IL2P unit test #########################


msg_str = 'What the fuck did you just fucking say about me, you little bitch? Ill have you know I graduated top of my class in the Navy Seals, and Ive been involved in numerous secret raids on Al-Quaeda, and I have over 300 confirmed kills.'
header = IL2P_Frame_Header(src_callsign='BAY   ', dst_callsign='WAY  !',\
                               hops=2, is_text_msg=True, is_beacon=True, \
                               acks=[True,False,False,True], \
                               request_ack=True, request_double_ack=True, \
                               payload_size=len(msg_str), data=np.array([10,0,12,600],dtype=np.uint16))

frame_to_send = frame_engine.encode_frame(header, np.frombuffer(msg_str.encode(),dtype=np.uint8))
corrupted_frame = inject_symbol_errors(frame_to_send, 0.99)

try:
    (header_received, decode_success, payload_received) = frame_engine.decode_frame(corrupted_frame)
    header_received = frame_engine.decode_header(corrupted_frame[0:IL2P.IL2P_HDR_LEN_ENC])
except exceptions.IL2PHeaderDecodeError:
    print('FAILURE: header could not be decoded')

if not(header.equals(header_received)):
    print('FAILURE: headers do not match')
print(payload_received.tobytes().decode())

###############################################

frame_engine = IL2P_Frame_Engine()
msg_str = 'message'
header = IL2P_Frame_Header(src_callsign='BAX',dst_callsign='WAYG',payload_size=len(msg_str))

frame_to_send = frame_engine.encode_frame(header, np.frombuffer(msg_str.encode(),dtype=np.uint8))
corrupted_frame = inject_symbol_errors(frame_to_send, 0.99)

try:
    (header_received, decode_success, payload_received) = frame_engine.decode_frame(corrupted_frame)
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
corrupted_frame = inject_symbol_errors(frame_to_send, 0.99)


try:
    (header_received, decode_success, payload_received) = frame_engine.decode_frame(corrupted_frame)
except exceptions.IL2PHeaderDecodeError:
    print('FAILURE: header could not be decoded')

if not(header.equals(header_received)):
    print('FAILURE: headers do not match')
print(payload_received)

