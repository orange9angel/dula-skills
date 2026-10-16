"""Regression for the public V3 wire contract (no paid API calls)."""
import base64, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from seedtts_say import synthesize, SeedTTSError

class RequestContract(unittest.TestCase):
    def test_director_controls_reach_native_fields(self):
        stream=io.BytesIO((json.dumps({'data':base64.b64encode(b'audio').decode()})+'\n'+json.dumps({'code':20000000})+'\n').encode())
        with tempfile.TemporaryDirectory() as d, patch('urllib.request.urlopen',return_value=stream) as post:
            path=synthesize('test','speaker',Path(d)/'sample.mp3',api_key='test-only',
                emotion='happy',emotion_scale=2,context_texts=['Speak warmly.'],speech_rate=4)
            req=json.loads(post.call_args.args[0].data)['req_params']
            self.assertNotIn('emotion',req)
            self.assertEqual(req['audio_params']['emotion'],'happy')
            self.assertEqual(req['audio_params']['emotion_scale'],2)
            self.assertEqual(req['audio_params']['speech_rate'],4)
            self.assertIsInstance(req['additions'],str)
            self.assertEqual(json.loads(req['additions'])['context_texts'],['Speak warmly.'])
            self.assertEqual(path.read_bytes(),b'audio')

    def test_empty_success_cannot_publish_audio(self):
        with tempfile.TemporaryDirectory() as d, patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"code":20000000}\n')):
            out=Path(d)/'sample.mp3'
            with self.assertRaises(SeedTTSError):synthesize('test','speaker',out,api_key='test-only')
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
