from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from .models import GeneratedReport
from detection.models import DetectionResult
from dron_map.models import Projects
from reports.tasks import generate_detection_report, generate_drone_report
from reports.signals import auto_generate_detection_report
from unittest.mock import patch
import os

class ReportTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other = User.objects.create_user(username='otheruser', password='password')
        self.client.login(username='testuser', password='password')
        
        self.detection = DetectionResult.objects.create(
            fruit_type="apple",
            tree_count=10,
            tree_age=5,
            detected_count=100,
            weight=10.5,
            total_weight=105.0,
            processing_time=1.2,
            image_path="test.jpg",
            created_by=self.user,
        )

        self.other_detection = DetectionResult.objects.create(
            fruit_type="apple",
            tree_count=10,
            tree_age=5,
            detected_count=100,
            weight=10.5,
            total_weight=105.0,
            processing_time=1.2,
            image_path="other.jpg",
            created_by=self.other,
        )

        self.other_project = Projects.objects.create(
            Farm="Other Farm",
            Field="Other Field",
            Title="Other Project",
            State="Active",
            created_by=self.other,
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
        bad_report = GeneratedReport.objects.create(
            report_type="detection",
            format="pdf",
            status="ready",
            file_path="../../etc/passwd"
        )
        response = self.client.get(reverse('reports:download', args=[bad_report.id]))
        self.assertEqual(response.status_code, 404)

    def test_delete_report(self):
        report_id = self.report.id
        
        response = self.client.post(reverse('reports:delete', args=[report_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GeneratedReport.objects.filter(id=report_id).exists())

    @patch('reports.tasks.generate_detection_report.delay')
    def test_request_detection_report_rejects_foreign_result(self, mock_task):
        mock_task.return_value.id = '456-task-id'
        data = {
            'detection_result_id': self.other_detection.id,
            'formats': ['pdf']
        }
        response = self.client.post(
            reverse('reports:request-detection'),
            data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_task.called)

    @patch('reports.views.get_latest_analysis_data')
    @patch('reports.tasks.generate_drone_report.delay')
    def test_request_drone_report_rejects_foreign_project(self, mock_task, mock_analysis):
        mock_task.return_value.id = '789-task-id'
        mock_analysis.return_value = {'project_id': self.other_project.id, 'stress_zones': []}
        data = {
            'project_id': self.other_project.id,
            'formats': ['pdf']
        }
        response = self.client.post(
            reverse('reports:request-drone'),
            data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_task.called)


class ReportTaskOwnershipTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.owner = User.objects.create_user(username='owner', password='password')
        self.intruder = User.objects.create_user(username='intruder', password='password')

        self.detection = DetectionResult.objects.create(
            fruit_type="apple",
            tree_count=10,
            tree_age=5,
            detected_count=100,
            weight=10.5,
            total_weight=105.0,
            processing_time=1.2,
            image_path="owner.jpg",
            created_by=self.owner,
        )

        self.project = Projects.objects.create(
            Farm="Owner Farm",
            Field="Owner Field",
            Title="Owner Project",
            State="Active",
            created_by=self.owner,
        )

        self.analysis_data = {'project_id': self.project.id, 'stress_zones': []}

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    @patch('reports.tasks.generate_detection_pdf', autospec=True)
    def test_detection_task_rejects_foreign_owner(self, mock_pdf):
        mock_pdf.return_value = 'reports/detection_foreign.pdf'
        result = generate_detection_report(
            self.detection.id, ['pdf'], user_id=self.intruder.pk
        )
        self.assertIsNone(result)
        self.assertFalse(mock_pdf.called)
        self.assertFalse(
            GeneratedReport.objects.filter(created_by=self.intruder).exists()
        )

    @patch('reports.tasks.generate_detection_pdf', autospec=True)
    def test_detection_task_accepts_owner(self, mock_pdf):
        mock_pdf.return_value = 'reports/detection_owner.pdf'
        result = generate_detection_report(
            self.detection.id, ['pdf'], user_id=self.owner.pk
        )
        self.assertEqual(result, {'pdf': 'reports/detection_owner.pdf'})
        report = GeneratedReport.objects.get(detection_result=self.detection)
        self.assertEqual(report.created_by, self.owner)
        self.assertEqual(report.status, 'ready')

    @patch('reports.tasks.generate_detection_pdf', autospec=True)
    def test_detection_task_allows_missing_user_id(self, mock_pdf):
        mock_pdf.return_value = 'reports/detection_signal.pdf'
        result = generate_detection_report(self.detection.id, ['pdf'])
        self.assertEqual(result, {'pdf': 'reports/detection_signal.pdf'})
        report = GeneratedReport.objects.get(detection_result=self.detection)
        self.assertIsNone(report.created_by)
        self.assertEqual(report.status, 'ready')

    @patch('reports.tasks.generate_drone_pdf', autospec=True)
    def test_drone_task_rejects_foreign_owner(self, mock_pdf):
        mock_pdf.return_value = 'reports/drone_foreign.pdf'
        result = generate_drone_report(
            self.project.id, self.analysis_data, ['pdf'], user_id=self.intruder.pk
        )
        self.assertIsNone(result)
        self.assertFalse(mock_pdf.called)
        self.assertFalse(
            GeneratedReport.objects.filter(created_by=self.intruder).exists()
        )

    @patch('reports.tasks.generate_drone_pdf', autospec=True)
    def test_drone_task_accepts_owner(self, mock_pdf):
        mock_pdf.return_value = 'reports/drone_owner.pdf'
        result = generate_drone_report(
            self.project.id, self.analysis_data, ['pdf'], user_id=self.owner.pk
        )
        self.assertEqual(result, {'pdf': 'reports/drone_owner.pdf'})
        report = GeneratedReport.objects.get(project=self.project)
        self.assertEqual(report.created_by, self.owner)
        self.assertEqual(report.status, 'ready')

    @patch('reports.tasks.generate_drone_pdf', autospec=True)
    def test_drone_task_allows_missing_user_id(self, mock_pdf):
        mock_pdf.return_value = 'reports/drone_beat.pdf'
        result = generate_drone_report(
            self.project.id, self.analysis_data, ['pdf']
        )
        self.assertEqual(result, {'pdf': 'reports/drone_beat.pdf'})
        report = GeneratedReport.objects.get(project=self.project)
        self.assertIsNone(report.created_by)
        self.assertEqual(report.status, 'ready')
