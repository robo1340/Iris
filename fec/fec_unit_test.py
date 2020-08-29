import numpy as np

import fec

encoder = fec.FramePayloadEncoder()
decoder = fec.FramePayloadDecoder()

msg_str = 'What the fuck did you just fucking say about me, you little bitch? Ill have you know I graduated top of my class in the Navy Seals, and Ive been involved in numerous secret raids on Al-Quaeda, and I have over 300 confirmed kills. I am trained in gorilla warfare and Im the top sniper in the entire US armed forces. You are nothing to me but just another target. I will wipe you the fuck out with precision the likes of which has never been seen before on this Earth, mark my fucking words. You think you can get away with saying that shit to me over the Internet? Think again, fucker. As we speak I am contacting my secret network of spies across the USA and your IP is being traced right now so you better prepare for the storm, maggot. The storm that wipes out the pathetic little thing you call your life. Youre fucking dead, kid. I can be anywhere, anytime, and I can kill you in over seven hundred ways, and thats just with my bare hands. Not only am I extensively trained in unarmed combat, but I have access to the entire arsenal of the United States Marine Corps and I will use it to its full extent to wipe your miserable ass off the face of the continent, you little shit. If only you could have known what unholy retribution your little "clever" comment was about to bring down upon you, maybe you would have held your fucking tongue. But you couldnt, you didnt, and now youre paying the price, you goddamn idiot. I will shit fury all over you and you will drown in it. Youre fucking dead, kiddo'
msg = np.frombuffer(bytes(msg_str,'ascii'), dtype=np.uint8)

header = np.ones((1,13), dtype=np.uint8)

h_codec = fec.FrameHeaderCodec()
header_enc = h_codec.encode(header)
h_decoded = h_codec.decode(header_enc,True)
print(h_decoded[1])


for error_thresh in np.linspace(0.9,0.99,10):
	num_success = 0
	num_total = 10
	for i in range(0,10):
		msg_enc = encoder.encode(msg)
		msg_corrupted = fec.inject_symbol_errors(msg_enc,error_thresh) #simulate a noisy wireless channel
		msg_dec = decoder.decode(msg_corrupted,len(msg_str))
		if (msg_dec[0] == True):
			num_success += 1
	
	print('For error rate %f, decode success was %d/%d' % (1.0-error_thresh, num_success, num_total))
	
