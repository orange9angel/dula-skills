import unittest
import numpy as np
from bed_loop import bounded_bed

class BedLoopTest(unittest.TestCase):
    def test_exact_cue_length_and_fades(self):
        source=np.ones((1000,2))*.2
        for n in [10,250,2500]:
            out=bounded_bed(source,n,100,crossfade=1,fade_in=.1,fade_out=.1)
            self.assertEqual(out.shape,(n,2));self.assertTrue(np.isfinite(out).all())
            self.assertTrue(np.all(out[0]==0));self.assertTrue(np.all(out[-1]==0));self.assertLessEqual(out.max(),.200001)
    def test_zero_crossfade(self):
        source=np.arange(20).reshape(10,2)/20
        out=bounded_bed(source,15,100,crossfade=0,fade_in=0,fade_out=0)
        np.testing.assert_array_equal(out[:10],source);np.testing.assert_array_equal(out[10:],source[:5])
if __name__=='__main__':unittest.main()
