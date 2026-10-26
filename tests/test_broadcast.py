import unittest
from unittest.mock import patch
import numpy as np
from broadcast import BroadcastBus
from audio_engine import AudioEngine,Clip

class BroadcastTests(unittest.TestCase):
 def test_live_mic_mix_and_block_voice_and_limit(self):
  active=[True]
  bus=BroadcastBus(lambda out,frames:out.fill(.2),lambda:active[0]);bus.mic_gain=.6
  mic=np.full((8,1),.5,dtype=np.float32);out=np.empty((8,2),dtype=np.float32)
  bus.mix(mic,out,8);self.assertTrue(np.allclose(out,.5))
  bus.block_voice=True;bus.mix(mic,out,8);self.assertTrue(np.allclose(out,.2))
  active[0]=False;bus.mix(mic,out,8);self.assertTrue(np.allclose(out,.5))
  bus.block_voice=False;bus.mic_gain=4;bus.mix(mic,out,8);self.assertTrue(np.all(out==1))
 def test_file_only_and_silence_keep_live_bus(self):
  engine=AudioEngine();engine.broadcast_gain=.5
  data=np.full((3,2),.4,dtype=np.float32)
  engine.broadcast_track=dict(data=data,rate=48000,position=0,role='broadcast')
  engine.tracks=[engine.broadcast_track];out=np.empty((5,2),dtype=np.float32)
  engine.bus.mix(None,out,5)
  self.assertTrue(np.allclose(out[:3],.2));self.assertTrue(np.all(out[3:]==0))
  engine.stop();engine.bus.mix(np.full((5,1),.3,dtype=np.float32),out,5)
  self.assertTrue(np.allclose(out,.3));self.assertFalse(engine.playing)
 def test_different_host_apis_fail_without_opening_input(self):
  bus=BroadcastBus(lambda out,n:None,lambda:False)
  with patch('broadcast.sd.query_devices',side_effect=[{'hostapi':0,'max_output_channels':2,'default_samplerate':48000},{'hostapi':1,'max_input_channels':1,'default_samplerate':48000}]),patch('broadcast.sd.Stream') as stream:
   with self.assertRaisesRegex(ValueError,'same audio'):bus.start(2,1)
   stream.assert_not_called()
 def test_failed_stream_start_closes_resources(self):
  bus=BroadcastBus(lambda out,n:None,lambda:False)
  class Broken:
   closed=False
   def start(self):raise RuntimeError('gone')
   def close(self):self.closed=True
  fake=Broken()
  with patch('broadcast.sd.query_devices',return_value={'hostapi':0,'max_output_channels':2,'default_samplerate':48000}),patch('broadcast.sd.check_output_settings'),patch('broadcast.sd.OutputStream',return_value=fake):
   with self.assertRaises(RuntimeError):bus.start(2)
   self.assertTrue(fake.closed);self.assertFalse(bus.active)

if __name__=='__main__':unittest.main(verbosity=2)
