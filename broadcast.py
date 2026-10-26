"""Continuous virtual-microphone bus. Mixes live input with file audio locally."""
import numpy as np
import sounddevice as sd


def input_devices():
    apis=sd.query_hostapis()
    return [dict(index=i,name=d['name'],api=apis[d['hostapi']]['name'],rate=int(d['default_samplerate']),channels=int(d['max_input_channels']))
            for i,d in enumerate(sd.query_devices()) if d['max_input_channels']>0]


class BroadcastBus:
    def __init__(self, render_file, file_active):
        self.render_file=render_file
        self.file_active=file_active
        self.stream=None
        self.output_device=None
        self.input_device=None
        self.rate=48000
        self.channels=2
        self.mic_gain=1.0
        self.block_voice=False
        self.mic_peak=0.0
        self.warning=''

    @property
    def active(self):return self.stream is not None

    def mix(self, indata, outdata, frames):
        file_is_active=self.file_active()
        self.render_file(outdata,frames)
        if indata is not None:
            self.mic_peak=float(np.max(np.abs(indata))) if indata.size else 0
            if not (self.block_voice and file_is_active):
                mono=indata.mean(axis=1)*self.mic_gain
                for channel in range(outdata.shape[1]):outdata[:,channel]+=mono
        np.clip(outdata,-1,1,out=outdata)

    def start(self,output_device,input_device=None):
        self.stop()
        if output_device is None:raise ValueError('Select a virtual cable output such as CABLE Input for broadcast.')
        output=sd.query_devices(output_device,'output')
        input_info=sd.query_devices(input_device,'input') if input_device is not None else None
        if input_info is not None and input_info['hostapi']!=output['hostapi']:
            raise ValueError('The microphone and broadcast output must use the same audio backend. Select WASAPI for both.')
        self.channels=min(2,int(output['max_output_channels']))
        in_channels=min(2,int(input_info['max_input_channels'])) if input_info else 0
        rates=list(dict.fromkeys([48000,int(output['default_samplerate']),44100]))
        rate_error=None
        for rate in rates:
            try:
                sd.check_output_settings(device=output_device,channels=self.channels,dtype='float32',samplerate=rate)
                if input_info:sd.check_input_settings(device=input_device,channels=in_channels,dtype='float32',samplerate=rate)
                self.rate=rate;break
            except Exception as e:rate_error=e
        else:raise ValueError('The microphone and virtual cable could not use a common sample rate: '+str(rate_error))
        self.output_device=int(output_device)
        self.input_device=input_device
        self.warning=''
        stream=None
        try:
            if input_info:
                def callback(indata,outdata,frames,timing,status):
                    if status:self.warning=str(status)
                    self.mix(indata,outdata,frames)
                stream=sd.Stream(device=(input_device,output_device),channels=(in_channels,self.channels),
                                 samplerate=self.rate,dtype='float32',latency='high',callback=callback)
            else:
                def callback(outdata,frames,timing,status):
                    if status:self.warning=str(status)
                    self.mix(None,outdata,frames)
                stream=sd.OutputStream(device=output_device,channels=self.channels,samplerate=self.rate,
                                       dtype='float32',latency='high',callback=callback)
            self.stream=stream
            stream.start()
        except Exception:
            self.stream=None
            if stream is not None:
                try:stream.close()
                except Exception:pass
            raise

    def stop(self):
        stream,self.stream=self.stream,None
        if stream is not None:
            try:stream.abort()
            except Exception as err:self.warning=str(err)
            try:stream.close()
            except Exception as err:self.warning=str(err)
        self.mic_peak=0
