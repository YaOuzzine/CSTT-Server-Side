from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('generate-test-case/', views.test_cases, name='generate_test_case'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', views.VerifyTokenView.as_view(), name='verify-token'),
    path('save-test-case/', views.SaveTestCaseView.as_view(), name='save_test_case'),
    path('save-test-steps/', views.SaveTestStepsView.as_view(), name='save_test_steps'),
    path("teams/<uuid:team_id>/generate-invite/", views.GenerateInviteView.as_view(), name="generate_invite"),
    path("teams/join/", views.JoinTeamView.as_view(), name="join_team"),
    path("teams/member/", views.MemberTeamsView.as_view(), name="member_teams"),
    path("teams/create/", views.CreateTeamView.as_view(), name="create_team"),
    path("teams/<uuid:team_id>/", views.TeamDetailsView.as_view(), name="team_details"),
    path("teams/<uuid:team_id>/projects/create/", views.CreateProjectView.as_view(), name="create_project"),
    path("teams/<uuid:team_id>/projects/", views.TeamProjectsView.as_view(), name="team_projects"),
    path("teams/latest/", views.LatestTeamsView.as_view(), name="latest_teams"),
    path("projects/<uuid:project_id>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path('projects/<uuid:project_id>/test-suites/', views.TestSuiteListView.as_view(), name='test_suites_list'),
    path('projects/<uuid:project_id>/test-suites/create/', views.CreateTestSuiteView.as_view(), name='create_test_suite'),
    path('test-suites/<uuid:test_suite_id>/test-cases/', views.TestSuiteTestCasesView.as_view(), name='test_suite_test_cases'),
]
