import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from audio_engine import AudioEngine, Clip, load_clip, resample
from library import Library
from hotkeys import parse_hotkey

class CoreTests(unittest.TestCase):
    def test_decode_normalize_and_resample(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tone.wav'
            sf.write(path,np.full(4800,.1,dtype=np.float32),48000,subtype='FLOAT')
            clip=load_clip(str(path),True)
            self.assertEqual(clip.samples.shape,(4800,2))
            self.assertAlmostEqual(float(clip.samples.max()),.4,places=5)
            converted=resample(clip.samples,48000,44100)
            self.assertEqual(len(converted),4410)
            self.assertTrue(np.allclose(converted,.4))

    def test_playback_tail_loop_pause_seek(self):
        engine=AudioEngine();engine.preview_gain=.5
        data=np.array([[1,-1],[.4,-.4],[.2,-.2]],dtype=np.float32)
        track=dict(data=data,rate=10,position=0,role='preview');engine.tracks=[track]
        out=np.empty((5,2),dtype=np.float32)
        engine.render(track,out,5)
        self.assertTrue(np.allclose(out[:3],data*.5));self.assertTrue(np.all(out[3:]==0));self.assertFalse(engine.playing)
        engine.loop=True;track['position']=2;engine.render(track,out,5)
        self.assertTrue(np.allclose(out,np.vstack([data[2:],data,data[:1]])*.5))
        engine.paused=True;pos=track['position'];engine.render(track,out,5)
        self.assertTrue(np.all(out==0));self.assertEqual(pos,track['position'])
        engine.seek(.1);self.assertEqual(track['position'],1)

    def test_output_failure_releases_already_open_stream(self):
        closed=[]
        class Fake:
            def __init__(self,**kw):
                if kw['device']==2:raise RuntimeError('Cannot open second output')
            def start(self):pass
            def abort(self):closed.append('abort')
            def close(self):closed.append('close')
        with patch('audio_engine.sd.query_devices',return_value={'max_output_channels':2,'default_samplerate':48000}),patch('audio_engine.sd.OutputStream',Fake),patch('audio_engine.sd.default.device',[-1,1]):
            engine=AudioEngine()
            with self.assertRaises(RuntimeError):engine.play(Clip(np.ones((20,2),np.float32),48000,''),1,2,'both')
            self.assertEqual(closed,['abort','close']);self.assertEqual(engine.streams,[]);self.assertEqual(engine.tracks,[])

    def test_library_roundtrip_duplicate_and_corruption_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=Library(folder);file=Path(folder)/'audio.wav';file.write_bytes(b'fixture')
            added=lib.add(file);self.assertIsNotNone(added);self.assertIsNone(lib.add(file))
            lib.sounds[0]['hotkey']='Ctrl+Alt+1';lib.save()
            self.assertEqual(Library(folder).sounds[0]['hotkey'],'Ctrl+Alt+1')
            lib.path.write_text('{broken',encoding='utf-8')
            repaired=Library(folder)
            self.assertIn('Could not read',repaired.warning)
            self.assertEqual(list(Path(folder).glob('library.unreadable-*'))[0].read_text(),'{broken')

    def test_hotkey_validation(self):
        self.assertEqual(parse_hotkey('Ctrl+Alt+1'),(0x4003,49))
        self.assertEqual(parse_hotkey('Shift+F11'),(0x4004,122))
        for invalid in ['A','F12','Ctrl+F12','Ctrl+Alt+','Ctrl+Alt+1, Ctrl+2']:
            with self.assertRaises(ValueError):parse_hotkey(invalid)

if __name__=='__main__':unittest.main(verbosity=2)

