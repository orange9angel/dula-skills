import copy
import unittest
from bounded_staging_audit import audit_bounded_staging


class BoundedTest(unittest.TestCase):
    def setUp(self):
        self.config={'actors':['a','b'],'window':[0,.1],'min_actor_gap':.5,'min_environment_gap':.1,'min_camera_gap':.1,
            'max_bone_error':1e-6,'sole_y':[-.003,.01],'max_root_step':1e-6,'max_wrist_step':.03,
            'min_camera_distance':2,'max_arm_angle':61,'max_head_turn':.24,'min_self_gap':.006,'self_pairs':['arms'],
            'framing':[{'entries':[1],'target':'arm','min_pixels':50,'require_unblocked':True}]}
        a={'boneError':0,'soleY':[0,0],'minEnvironmentGap':1,'cameraDistance':3,'maxArmAngle':45,
            'headTurn':.1,'selfGaps':{'arms':.2},'vertices':200,'root':[0,0,0],'wrists':[[-.3,1,0],[.3,1,0]]}
        self.data={'fps':30,'frames':[{'t':round(i/30,3),'entry':1,'metrics':{'a':copy.deepcopy(a),'b':copy.deepcopy(a),
            'actorGap':1,'cameraEnvironmentGap':2,'focus':{'arm':{'projection':[0,0,.9],'pixels':70,'blocked':False}}}} for i in range(3)]}
    def test_valid(self):self.assertTrue(audit_bounded_staging(self.data,self.config)['passed'])
    def test_missing_and_invalid_fail_closed(self):
        for mode in ['frame','actor','nan','offgrid','zero_vertices','projection','duplicate']:
            with self.subTest(mode=mode):
                d=copy.deepcopy(self.data)
                if mode=='frame':d['frames'].pop(1)
                if mode=='actor':del d['frames'][1]['metrics']['a']
                if mode=='nan':d['frames'][1]['metrics']['a']['soleY'][0]=float('nan')
                if mode=='offgrid':d['frames'][1]['t']=.04
                if mode=='zero_vertices':d['frames'][1]['metrics']['a']['vertices']=0
                if mode=='projection':del d['frames'][1]['metrics']['focus']
                if mode=='duplicate':d['frames'][1]['t']=0
                self.assertFalse(audit_bounded_staging(d,self.config)['passed'])
    def test_physical_and_framing_failures(self):
        for field,bad in [('soleY',[-.02,0]),('minEnvironmentGap',0),('boneError',.02),('root',[.1,0,0]),
            ('wrists',[[0,1,0],[.3,1,0]]),('maxArmAngle',80),('selfGaps',{'arms':0}),('selfGaps',{})]:
            with self.subTest(field=field):
                d=copy.deepcopy(self.data);d['frames'][1]['metrics']['a'][field]=bad
                self.assertFalse(audit_bounded_staging(d,self.config)['passed'])
        for field,bad in [('projection',[0,1.2,.9]),('pixels',10),('blocked',True)]:
            d=copy.deepcopy(self.data);d['frames'][1]['metrics']['focus']['arm'][field]=bad
            self.assertFalse(audit_bounded_staging(d,self.config)['passed'])

if __name__=='__main__':unittest.main()
