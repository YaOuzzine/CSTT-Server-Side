from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models import Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auth_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', db_index=True)
    role = models.CharField(max_length=50, db_index=True)  # Indexed for role-based queries
    preferences = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['role', 'created_at']),  # For filtering users by role and join date
        ]

class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)  # For filtering active teams

    class Meta:
        indexes = [
            models.Index(fields=['name', 'is_active']),  # Common query pattern
            models.Index(fields=['created_at', 'is_active']),  # For timeline views
        ]
    
class TeamInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=64, unique=True)  # Secure token
    created_by = models.ForeignKey("Profile", on_delete=models.SET_NULL, null=True)
    expires_at = models.DateTimeField()  # Expiry for the invite
    is_active = models.BooleanField(default=True)

class TeamMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', db_index=True)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='team_memberships', db_index=True)
    role = models.CharField(max_length=50, db_index=True)  # For role-based queries
    joined_at = models.DateTimeField(auto_now_add=True, db_index=True)  # For membership timeline
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['team', 'profile', 'is_active']),  # Active membership checks
            models.Index(fields=['role', 'joined_at']),  # Role timeline analysis
        ]

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    status = models.CharField(max_length=50, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects', db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'is_active']),  # Active project status
            models.Index(fields=['team', 'status', 'is_active']),  # Team project status
        ]

class TestSuite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_suites', db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'is_active']),  # Active suites per project
            models.Index(fields=['name', 'project']),  # Suite lookup by name within project
        ]

class TestCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    priority = models.CharField(max_length=20, db_index=True)
    type = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=50, db_index=True)
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='test_cases', db_index=True)
    created_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)
    generation_query = models.TextField(null=True, blank=True)  # Store the query content
    input_image = models.ImageField(upload_to="test_cases/images/", null=True, blank=True)  # Optional image upload

    class Meta:
        indexes = [
            models.Index(fields=['suite', 'status', 'priority']),  # Common filtering pattern
            models.Index(fields=['created_at', 'status']),  # Timeline views
            models.Index(fields=['type', 'status']),  # Type-based filtering
        ]

class TestStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='steps', db_index=True)
    order_number = models.IntegerField(db_index=True)
    action = models.TextField()
    expected_result = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['test_case', 'order_number']),  # Ordered steps retrieval
            models.Index(fields=['test_case', 'is_active']),  # Active steps per test case
        ]
        ordering = ['order_number']

class TestExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='executions', db_index=True)
    executed_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, db_index=True)
    started_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, db_index=True)
    status = models.CharField(max_length=50, db_index=True)
    notes = models.TextField()
    environment_data = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['test_case', 'status']),  # Execution status queries
            models.Index(fields=['started_at', 'completed_at']),  # Duration analysis
            models.Index(fields=['executed_by_profile', 'status']),  # User execution stats
        ]

class StepResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(TestExecution, on_delete=models.CASCADE, related_name='step_results', db_index=True)
    test_step = models.ForeignKey(TestStep, on_delete=models.CASCADE, db_index=True)
    status = models.CharField(max_length=50, db_index=True)
    actual_result = models.TextField()
    notes = models.TextField()
    attachments = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['execution', 'status']),  # Results by execution
            models.Index(fields=['test_step', 'status']),  # Step performance analysis
        ]

class TestData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    data_template = models.JSONField()
    format_type = models.CharField(max_length=50, db_index=True)
    created_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    test_cases = models.ManyToManyField(TestCase, related_name='test_data')

    class Meta:
        indexes = [
            models.Index(fields=['format_type', 'is_active']),  # Active data by format
            models.Index(fields=['name', 'format_type']),  # Data lookup by name and format
        ]

class Defect(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    status = models.CharField(max_length=50, db_index=True)
    priority = models.CharField(max_length=20, db_index=True)
    severity = models.CharField(max_length=20, db_index=True)
    assigned_to_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name='assigned_defects', db_index=True)
    reported_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name='reported_defects', db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='defects', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    metadata = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'priority', 'severity']),  # Defect triage queries
            models.Index(fields=['project', 'status']),  # Project defect status
            models.Index(fields=['assigned_to_profile', 'status']),  # Assigned defects status
        ]

class DefectHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE, related_name='history', db_index=True)
    field_name = models.CharField(max_length=100, db_index=True)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_by_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['defect', 'field_name']),  # Field change history
            models.Index(fields=['defect', 'created_at']),  # Timeline of changes
        ]

class DefectLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE, related_name='test_case_links', db_index=True)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='defect_links', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['defect', 'test_case']),  # Defect-TestCase relationship lookup
        ]
        unique_together = ('defect', 'test_case')

class Analytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='analytics', db_index=True)
    test_suite = models.ForeignKey(TestSuite, on_delete=models.SET_NULL, null=True, related_name='analytics', db_index=True)
    test_case = models.ForeignKey(TestCase, on_delete=models.SET_NULL, null=True, related_name='analytics', db_index=True)
    recorded_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'recorded_at']),  # Time-series project analytics
            models.Index(fields=['test_suite', 'recorded_at']),  # Time-series suite analytics
            models.Index(fields=['test_case', 'recorded_at']),  # Time-series test case analytics
        ]

class AnalyticsDimension(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analytics = models.ForeignKey(Analytics, on_delete=models.CASCADE, related_name='dimensions', db_index=True)
    dimension_key = models.CharField(max_length=100, db_index=True)
    dimension_value = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['analytics', 'dimension_key']),  # Dimension lookup
            models.Index(fields=['dimension_key', 'dimension_value']),  # Value analysis
        ]

class AnalyticsMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analytics = models.ForeignKey(Analytics, on_delete=models.CASCADE, related_name='metrics', db_index=True)
    metric_name = models.CharField(max_length=100, db_index=True)
    metric_value = models.FloatField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['analytics', 'metric_name']),
            models.Index(fields=['metric_name', 'created_at']),
            models.Index(fields=['created_at', 'metric_value']),
            models.Index(fields=['analytics', 'created_at']),
            models.Index(fields=['metric_name', 'metric_value'])
        ]

class AnalyticsService:
    @classmethod
    def get_test_execution_metrics(cls, project_id):
        """
        Calculate test execution metrics for a given project
        """
        try:
            # Total test cases
            total_test_cases = TestCase.objects.filter(suite__project_id=project_id).count()
            
            # Test executions in the last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            test_executions = TestExecution.objects.filter(
                test_case__suite__project_id=project_id, 
                started_at__gte=thirty_days_ago
            )
            
            # Calculate metrics
            total_executions = test_executions.count()
            passed_executions = test_executions.filter(status='Passed').count()
            failed_executions = test_executions.filter(status='Failed').count()
            skipped_executions = test_executions.filter(status='Skipped').count()
            
            # Test coverage calculation
            test_coverage = (passed_executions / total_test_cases * 100) if total_test_cases > 0 else 0
            
            return {
                'total_test_cases': total_test_cases,
                'total_executions': total_executions,
                'passed_executions': passed_executions,
                'failed_executions': failed_executions,
                'skipped_executions': skipped_executions,
                'test_coverage': round(test_coverage, 2)
            }
        except Exception as e:
            print(f"Error in test execution metrics: {e}")
            return {
                'total_test_cases': 0,
                'total_executions': 0,
                'passed_executions': 0,
                'failed_executions': 0,
                'skipped_executions': 0,
                'test_coverage': 0
            }
    
    @classmethod
    def get_defect_metrics(cls, project_id):
        """
        Calculate defect metrics for a given project
        """
        try:
            defects = Defect.objects.filter(project_id=project_id)
            
            # Defect count by severity with safe defaults
            defect_distribution = list(defects.values('severity').annotate(
                count=Count('id')
            ))
            
            # Ensure all severity levels are represented
            severity_levels = ['Critical', 'High', 'Medium', 'Low']
            distribution_dict = {item['severity']: item['count'] for item in defect_distribution}
            full_distribution = [
                {'severity': level, 'count': distribution_dict.get(level, 0)}
                for level in severity_levels
            ]
            
            # Defect resolution metrics
            total_defects = defects.count()
            open_defects = defects.filter(status__in=['Open', 'In Progress']).count()
            closed_defects = defects.filter(status='Closed').count()
            
            # Average time to resolve defects
            resolved_defects = defects.filter(status='Closed')
            avg_resolution = resolved_defects.aggregate(
                avg_time=Avg(F('updated_at') - F('created_at'))
            )
            avg_resolution_time = str(avg_resolution['avg_time']) if avg_resolution['avg_time'] else 'N/A'
            
            return {
                'total_defects': total_defects,
                'open_defects': open_defects,
                'closed_defects': closed_defects,
                'defect_distribution': full_distribution,
                'avg_resolution_time': avg_resolution_time
            }
        except Exception as e:
            print(f"Error in defect metrics: {e}")
            return {
                'total_defects': 0,
                'open_defects': 0,
                'closed_defects': 0,
                'defect_distribution': [
                    {'severity': 'Critical', 'count': 0},
                    {'severity': 'High', 'count': 0},
                    {'severity': 'Medium', 'count': 0},
                    {'severity': 'Low', 'count': 0}
                ],
                'avg_resolution_time': 'N/A'
            }
    
    @classmethod
    def get_test_execution_trend(cls, project_id):
        """
        Get daily test execution trend for the last 14 days
        """
        try:
            fourteen_days_ago = timezone.now() - timedelta(days=14)
            
            # Generate a full 14-day trend with zero values if no executions
            base_dates = [fourteen_days_ago + timedelta(days=x) for x in range(14)]
            
            # Get actual execution data
            execution_trend = TestExecution.objects.filter(
                test_case__suite__project_id=project_id,
                started_at__gte=fourteen_days_ago
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                passed=Count('id', filter=Q(status='Passed')),
                failed=Count('id', filter=Q(status='Failed')),
                skipped=Count('id', filter=Q(status='Skipped'))
            ).order_by('date')
            
            # Convert to list and create a complete 14-day trend
            trend_dict = {
                item['date'].strftime('%Y-%m-%d'): {
                    'passed': item['passed'],
                    'failed': item['failed'],
                    'skipped': item['skipped']
                } 
                for item in execution_trend
            }
            
            full_trend = [
                {
                    'date': date.strftime('%Y-%m-%d'),
                    'passed': trend_dict.get(date.strftime('%Y-%m-%d'), {}).get('passed', 0),
                    'failed': trend_dict.get(date.strftime('%Y-%m-%d'), {}).get('failed', 0),
                    'skipped': trend_dict.get(date.strftime('%Y-%m-%d'), {}).get('skipped', 0)
                }
                for date in base_dates
            ]
            
            return full_trend
        except Exception as e:
            print(f"Error in test execution trend: {e}")
            return []