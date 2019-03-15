def measureLight(serialPortName):
    import serial, numpy as np
    mySerial = serial.Serial(serialPortName, 115200, timeout=1)
    nSamples = 250
    sampleSum = 0
    for i in range(nSamples):
        mySerial.write(b'V')
        Response = mySerial.read(4)
        sampleSum += np.frombuffer(Response, dtype=np.uint32)
    meanValue = sampleSum.astype(np.float32)/nSamples
    print(meanValue)
