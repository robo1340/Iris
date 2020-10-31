import numpy as np
import pylab


data = np.memmap("temp.pcm", dtype='h', mode='r')
print (data)
x = range(len(data))
#pylab.scatter(x,data)
pylab.plot(data)
pylab.show()