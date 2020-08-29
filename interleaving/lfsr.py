import numpy as np

class LFSR():

	def __init__(self, fpoly=[9, 4], initstate=[0,0,0,0,0,1,1,1,1], outbit_ind=5):
		initstate = np.array(initstate)
		self.initstate = initstate
		self.fpoly = fpoly
		self.fpoly.sort(reverse=True)
		self.state = initstate.astype(int)
		self.outbit = -1
		self.outbit_ind = outbit_ind
		
		feed = ' '
		for i in range(len(self.fpoly)):
			feed = feed + 'x^' + str(self.fpoly[i]) + ' + '
		feed = feed + '1'
		self.feedpoly = feed

		self.check()

	def info(self):
		print('%d bit LFSR with feedback polynomial %s' % (self.initstate.shape[0], self.feedpoly))
		print('Current :')
		print(' State        : ', self.state)
		print(' Output bit   : ', self.outbit)

	def check(self):
		if np.max(self.fpoly) > self.initstate.shape[0] or np.min(self.fpoly) < 1 or len(self.fpoly) < 2:
			raise ValueError('Wrong feedback polynomial')
		if len(self.initstate.shape) > 1 and (self.initstate.shape[0] != 1 or self.initstate.shape[1] != 1):
			raise ValueError('Size of intial state vector should be one dimensional')
		else:
			self.initstate = np.squeeze(self.initstate)

	def reset(self):
		self.__init__(initstate=self.initstate, fpoly=self.fpoly)
		
	def setState(self, new_state):
		self.state = new_state
	
	def getState(self):
		return self.state

	def next(self,input_bit=0):
		prev_state = self.state
		self.state = np.roll(self.state, 1)
	
		#xor the value of the last register in the LFSR with its closest tap and save into the next register in the state
		#the index of the last register is self.fpolyp[0]-1
		#the index of the register feeding to the tap closest to the last register is self.fpoly[1]
		self.state[self.fpoly[1]+1] = np.logical_xor(prev_state[self.fpoly[0] - 1], prev_state[self.fpoly[1]]) * 1
		
		if len(self.fpoly) > 2:
			for i in range(2, len(self.fpoly)):
				b = np.logical_xor(prev_state[self.fpoly[0] - 1], prev_state[self.fpoly[i]])
				self.state[self.fpoly[i]] = b * 1

		self.state[0] = np.logical_xor(prev_state[self.fpoly[0]-1], input_bit) * 1
		self.outbit = self.state[self.outbit_ind]
		
		return self.outbit
