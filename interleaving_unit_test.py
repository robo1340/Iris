from interleaving.Interleaver import Interleaver, Deinterleaver
import numpy as np

scram = Interleaver()
descram = Deinterleaver()

arr = [0x2b,0xa1,0x12,0x24,0x25,0x77,0x6b,0x2b,0x54,0x68,0x25,0x2a,0x27]
bytes1a = np.array(arr, dtype=np.uint8)
bytes1b = descram.descramble_bits(scram.scramble_bits(bytes1a))

for i in range(0,len(bytes1a)):
	if (bytes1a[i] != bytes1b[i]):
		raise ValueError('values do not match after scrambling and descrambling the message')
print('Test 1 complete')

scram.reset()
descram.reset()

bytes2a = np.random.randint(0, 256, size=100)
bytes2b = descram.descramble_bits(scram.scramble_bits(bytes2a))

for i in range(0,len(bytes2a)):
	if (bytes2a[i] != bytes2b[i]):
		raise ValueError('values do not match after scrambling and descrambling the message')
print('Test 2 complete')

scram.reset()
descram.reset()

bytes3a = np.random.randint(0, 256, size=100)
bytes3b = descram.descramble_bits(scram.scramble_bits(bytes3a))

for i in range(0,len(bytes3a)):
	if (bytes3a[i] != bytes3b[i]):
		raise ValueError('values do not match after scrambling and descrambling the message')
print('Test 3 complete')