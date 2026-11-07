import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from ultralytics.engine.results import Results

from app.db import AlertDatabase
from src.pipeline import process_video
from src.config import load_config
import yaml


class FixtureDetector:
    """Deterministic detections, real ByteTrack/video/event/persistence components."""
    def __call__(self, frame):
        persons=Results(frame,path='',names={0:'person'},
                        boxes=np.array([[30,20,210,230,.95,0]],dtype=np.float32),
                        keypoints=np.zeros((1,17,3),dtype=np.float32))
        phones=Results(frame,path='',names={67:'cell phone'},
                       boxes=np.array([[130,130,155,165,.8,67]],dtype=np.float32))
        return persons,phones


class FixtureHeadDetector:
    def __init__(self):
        self.frame=0

    def __call__(self,frame):
        keypoints=np.zeros((2,17,3),dtype=np.float32)
        for index,cx in enumerate((80,230)):
            dx=12 if index==0 and self.frame>=6 else 0
            for k,x,y in [(0,cx+dx,100),(1,cx+dx-5,95),(2,cx+dx+5,95),
                          (3,cx-10,100),(4,cx+10,100),(5,cx-30,150),(6,cx+30,150)]:
                keypoints[index,k]=[x,y,.95]
        self.frame+=1
        persons=Results(frame,path='',names={0:'person'},
                        boxes=np.array([[25,10,145,230,.95,0],[170,10,290,230,.95,0]],dtype=np.float32),
                        keypoints=keypoints)
        phones=Results(frame,path='',names={67:'cell phone'},boxes=np.empty((0,6),dtype=np.float32))
        return persons,phones


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.video=self.root/'fixture.mp4'
        writer=cv2.VideoWriter(str(self.video),cv2.VideoWriter_fourcc(*'mp4v'),24,(320,240))
        if not writer.isOpened():
            self.skipTest('No MP4 writer on this platform')
        for _ in range(24):
            writer.write(np.zeros((240,320,3),dtype=np.uint8))
        writer.release()

    def tearDown(self):
        self.tmp.cleanup()

    def test_red_screenshot_database_and_repeated_video(self):
        notifications=[]
        def callback(kind,value):
            if kind=='event':
                notifications.append(value)
        first=process_video(self.video,self.root/'outputs',detector=FixtureDetector(),callback=callback)
        self.assertEqual(first['frames'],24)
        self.assertEqual(len(first['events']),1)
        self.assertEqual(len(notifications),1)
        event=first['events'][0]
        image=cv2.imread(str(self.root/'outputs'/event['screenshot_path']))
        self.assertIsNotNone(image)
        red=(image[:,:,2]>150)&(image[:,:,1]<80)&(image[:,:,0]<80)
        self.assertGreater(int(red.sum()),100)
        second=process_video(self.video,self.root/'outputs',detector=FixtureDetector())
        self.assertEqual(len(second['events']),1)
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertNotEqual(event['screenshot_path'],second['events'][0]['screenshot_path'])
        database=AlertDatabase(self.root/'outputs'/'cheating_alerts.db')
        self.assertEqual(len(database.get_alerts()),2)
        capture=cv2.VideoCapture(str(Path(first['output_directory'])/'annotated.mp4'))
        self.assertTrue(capture.read()[0])
        capture.release()

    def test_failed_screenshot_does_not_create_database_event(self):
        with patch('cv2.imwrite',return_value=False):
            with self.assertRaises(IOError):
                process_video(self.video,self.root/'outputs',detector=FixtureDetector())
        self.assertFalse(AlertDatabase(self.root/'outputs'/'cheating_alerts.db').get_alerts())

    def test_head_event_uses_real_persistence_and_notification_path(self):
        config=load_config()
        config.update(layer=1,head_baseline_s=.1,head_baseline_min_samples=3,
                      head_sustained_s=.25,head_min_episode_s=.08)
        path=self.root/'head_test.yaml'
        path.write_text(yaml.safe_dump(config))
        notifications=[]
        def callback(kind,value):
            if kind=='event':notifications.append(value)
        result=process_video(self.video,self.root/'outputs',path,callback=callback,detector=FixtureHeadDetector())
        self.assertEqual(len(result['events']),1)
        event=result['events'][0]
        self.assertEqual(event['behavior_type'],'peer_directed_looking')
        self.assertEqual(event['track_id'],1)
        self.assertEqual(len(notifications),1)
        self.assertIsNotNone(cv2.imread(str(self.root/'outputs'/event['screenshot_path'])))
        self.assertEqual(AlertDatabase(self.root/'outputs'/'cheating_alerts.db').get_alert_by_id(event['id'])['behavior_type'],'peer_directed_looking')


if __name__=='__main__':
    unittest.main()
