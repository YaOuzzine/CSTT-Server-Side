from django.contrib import admin
from .models import (
    Profile, Team, TeamMember, Project, TestSuite, TestCase, TestStep,
    TestExecution, StepResult, TestData, Defect, DefectHistory, DefectLink,
    Analytics, AnalyticsDimension, AnalyticsMetric
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('auth_user', 'role', 'created_at', 'updated_at')
    search_fields = ('auth_user__username', 'role')
    list_filter = ('role', 'created_at')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'created_by_profile', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active', 'created_at')

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('team', 'profile', 'role', 'joined_at', 'is_active')
    search_fields = ('team__name', 'profile__auth_user__username', 'role')
    list_filter = ('role', 'is_active', 'joined_at')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'team', 'created_at', 'is_active')
    search_fields = ('name', 'description', 'team__name')
    list_filter = ('status', 'is_active', 'created_at')

@admin.register(TestSuite)
class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'created_at', 'is_active')
    search_fields = ('name', 'description', 'project__name')
    list_filter = ('is_active', 'created_at')

@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'suite', 'priority', 'type', 'status', 'created_at', 'is_active')
    search_fields = ('title', 'description', 'suite__name')
    list_filter = ('priority', 'type', 'status', 'is_active')

@admin.register(TestStep)
class TestStepAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'order_number', 'is_active')
    search_fields = ('test_case__title', 'action', 'expected_result')
    list_filter = ('is_active',)
    ordering = ['test_case', 'order_number']

@admin.register(TestExecution)
class TestExecutionAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'executed_by_profile', 'started_at', 'completed_at', 'status')
    search_fields = ('test_case__title', 'notes')
    list_filter = ('status', 'started_at')
    ordering = ['-started_at']

@admin.register(StepResult)
class StepResultAdmin(admin.ModelAdmin):
    list_display = ('execution', 'test_step', 'status', 'created_at')
    search_fields = ('actual_result', 'notes')
    list_filter = ('status', 'created_at')
    ordering = ['-created_at']

@admin.register(TestData)
class TestDataAdmin(admin.ModelAdmin):
    list_display = ('name', 'format_type', 'created_by_profile', 'created_at', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('format_type', 'is_active', 'created_at')
    ordering = ['-created_at']

@admin.register(Defect)
class DefectAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'priority', 'severity', 'assigned_to_profile', 'project', 'created_at', 'is_active')
    search_fields = ('title', 'description')
    list_filter = ('status', 'priority', 'severity', 'is_active')
    ordering = ['-created_at']

@admin.register(DefectHistory)
class DefectHistoryAdmin(admin.ModelAdmin):
    list_display = ('defect', 'field_name', 'changed_by_profile', 'created_at')
    search_fields = ('defect__title', 'field_name', 'old_value', 'new_value')
    list_filter = ('field_name', 'created_at')
    ordering = ['-created_at']

@admin.register(DefectLink)
class DefectLinkAdmin(admin.ModelAdmin):
    list_display = ('defect', 'test_case', 'created_at')
    search_fields = ('defect__title', 'test_case__title')
    list_filter = ('created_at',)
    ordering = ['-created_at']

@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'test_suite', 'test_case', 'recorded_at', 'is_active')
    search_fields = ('name', 'project__name')
    list_filter = ('is_active', 'recorded_at')
    ordering = ['-recorded_at']

@admin.register(AnalyticsDimension)
class AnalyticsDimensionAdmin(admin.ModelAdmin):
    list_display = ('analytics', 'dimension_key', 'dimension_value', 'created_at')
    search_fields = ('analytics__name', 'dimension_key', 'dimension_value')
    list_filter = ('created_at',)
    ordering = ['-created_at']

@admin.register(AnalyticsMetric)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = ('analytics', 'metric_name', 'metric_value', 'created_at')
    search_fields = ('analytics__name', 'metric_name')
    list_filter = ('created_at',)
    ordering = ['-created_at']