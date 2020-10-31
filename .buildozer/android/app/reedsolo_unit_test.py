from fec.reedsolo import RSCodec, ReedSolomonError


rsc = RSCodec(10)  # 10 ecc symbols

msg_str = 'message' #message to send

msg = bytes(msg_str, 'ascii') #message as bytes
msg_enc = rsc.encode(msg) #message encoded with Reed Solomon error correction symbols appended

#tamper with the message
msg_corrupted = bytearray(len(msg_enc))
msg_corrupted[:] = msg_enc #copy the encoded message to a new array to be tampered with

#msg_corrupted[1] = 0
msg_corrupted[5] = 0
msg_corrupted[11] = 0
msg_corrupted[9] = 0
msg_corrupted[13] = 0
msg_corrupted[14] = 0


msg_dec = bytes(' ','ascii')
try:
	msg_dec = rsc.decode(msg_corrupted)[0] #decode the message
except ReedSolomonError:
  print("Reed Solomon Decoding failed")


print('original message string: %s' % (msg_str))
print('original message in hex: %s' % (msg.hex()))
print('encoded message in hex : %s' % (msg_enc.hex()))
print('tampered message in hex: %s' % (msg_corrupted.hex()))
print('decoded message string : %s' % (msg_dec.decode("ascii") ))