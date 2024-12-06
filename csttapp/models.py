from django.db import models
from django.contrib.auth.models import User
import uuid

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