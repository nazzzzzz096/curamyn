from piper import PiperVoice

voice = PiperVoice.load("models/en_US-amy-low.onnx")

for chunk in voice.synthesize("Hello"):
    print(type(chunk))
    print(dir(chunk))
    break
