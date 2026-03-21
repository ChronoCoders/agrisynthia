from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from .models import GeneratedReport
from detection.models import DetectionResult
# Import the signal handler to disconnect it
from reports.signals import auto_generate_detection_report
from unittest.mock import patch
import os

class ReportTests(TestCase):
    def setUp(self):
        # Disconnect signal to avoid Celery/Redis connection during test setup
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        
        self.detection = DetectionResult.objects.create(
            fruit_type="apple",
            tree_count=10,
            tree_age=5,
            detected_count=100,
            weight=10.5,
            total_weight=105.0,
            processing_time=1.2,
            image_path="test.jpg"
        )
        
        self.report = GeneratedReport.objects.create(
            report_type="detection",
            detection_result_id=self.detection.id,
            format="pdf",
            status="ready",
            file_path="/tmp/test_report.pdf",
            created_by=self.user,
        )

    def tearDown(self):
        # Reconnect signal after tests
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def test_report_list_view(self):
        response = self.client.get(reverse('reports:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rapor Listesi")
        self.assertContains(response, "Hazır")  # status label for 'ready' reports

    @patch('reports.tasks.generate_detection_report.delay')
    def test_request_detection_report(self, mock_task):
        mock_task.return_value.id = '123-task-id'
        data = {
            'detection_result_id': self.detection.id,
            'formats': ['pdf']
        }
        response = self.client.post(
            reverse('reports:request-detection'),
            data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(mock_task.called)

    def test_download_report_path_traversal(self):
        # Create a malicious report entry
        bad_report = GeneratedReport.objects.create(
            report_type="detection",
            format="pdf",
            status="ready",
            file_path="../../etc/passwd"
        )
        response = self.client.get(reverse('reports:download', args=[bad_report.id]))
        self.assertEqual(response.status_code, 404)

    def test_delete_report(self):
        # Setup file and report
        report_id = self.report.id
        
        response = self.client.post(reverse('reports:delete', args=[report_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GeneratedReport.objects.filter(id=report_id).exists())
