import os
import json
from openai import OpenAI
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string
from django.utils.timezone import now, timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import Team, TeamInvite, TeamMember, Profile, Project, TestSuite, TestCase
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserRegistrationSerializer, UserLoginSerializer, TestCaseSerializer, TestStepBatchSerializer, TeamSerializer, ProjectSerializer, TestSuiteSerializer


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        print("Registering...: ", request.data)
        serializer = UserRegistrationSerializer(data=request.data)
        
        print("Serialized!")
        if serializer.is_valid():
            user = serializer.save()
            print("user saved")
            # Generate tokens
            
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': f"{user.first_name} {user.last_name}".strip(),
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        print("Login Serialized!")
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            # Get user by email
            try:
                print("Getting user...")
                user = User.objects.get(email=email)
                print("Got the user!", user)
            except User.DoesNotExist:
                return Response({
                    'error': 'Invalid email or password'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Authenticate using username (email) and password
            print("Authenticating the user!")
            user = authenticate(username=user.username, password=password)
            
            print("User authenticated!", user)
            
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'token': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'full_name': f"{user.first_name} {user.last_name}".strip(),
                    }
                })
            
            return Response({
                'error': 'Invalid email or password'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyTokenView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # If the request reaches here, the token is valid
        # (IsAuthenticated permission class handles the validation)
        return Response({
            'valid': True,
            'user': {
                'id': request.user.id,
                'email': request.user.email,
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip()
            }
        })

class GenerateInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, team_id):
        profile = request.user.profile
        team = get_object_or_404(Team, id=team_id)

        # Check if user is part of the team
        if not team.members.filter(profile=profile).exists():
            return Response({"error": "You are not a member of this team"}, status=403)

        token = get_random_string(32)
        expires_at = now() + timedelta(days=7)
        invite = TeamInvite.objects.create(
            team=team, token=token, created_by=profile, expires_at=expires_at
        )
        invite_link = f"{request.scheme}://{request.get_host()}/teams/join?invite={token}"
        return Response({"invite_link": invite_link})

class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.query_params.get("invite")
        if not token:
            return Response({"error": "Invalid invite link"}, status=400)

        try:
            invite = TeamInvite.objects.get(token=token, is_active=True)
        except TeamInvite.DoesNotExist:
            return Response({"error": "Invalid or expired invite link"}, status=400)

        # Check if invite has expired
        if invite.expires_at < now():
            invite.is_active = False
            invite.save()
            return Response({"error": "Invite link has expired"}, status=400)

        # Add user to the team
        profile = request.user.profile
        if invite.team.members.filter(profile=profile).exists():
            return Response({"message": "You are already a member of this team"}, status=200)

        TeamMember.objects.create(team=invite.team, profile=profile, role="Member")
        return Response({"message": f"You have successfully joined {invite.team.name}"})

class MemberTeamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get the current user's profile
        profile = request.user.profile

        # Query teams where the user is a member
        member_teams = Team.objects.filter(members__profile=profile, is_active=True)

        # Serialize the results
        serializer = TeamSerializer(member_teams, many=True)
        return Response(serializer.data)

class CreateTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Get the authenticated user's profile
            profile = Profile.objects.get(auth_user=request.user)

            # Create the team
            team = Team.objects.create(
                name=request.data["name"],
                description=request.data["description"],
                is_active=request.data.get("is_active", True),
                created_by_profile=profile,
            )

            # Add the creator as a member of the team
            TeamMember.objects.create(
                team=team,
                profile=profile,
                role="Owner",  # Assign the creator an 'Owner' role
                is_active=True,
            )

            # Serialize the created team
            serializer = TeamSerializer(team)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class TeamProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        try:
            # Ensure the team exists
            team = Team.objects.get(id=team_id)

            # Fetch projects related to the team
            projects = Project.objects.filter(team=team, is_active=True)
            serializer = ProjectSerializer(projects, many=True)

            return Response(serializer.data, status=200)
        except Team.DoesNotExist:
            return Response({"error": "Team not found."}, status=404)

class LatestTeamsView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get the user's profile
        user_profile = request.user.profile

        # Fetch the latest 3 teams based on `joined_at`
        latest_team_memberships = (
            TeamMember.objects.filter(profile=user_profile, is_active=True)
            .order_by("-joined_at")[:3]
        )

        # Extract the teams and serialize
        latest_teams = [membership.team for membership in latest_team_memberships]
        serializer = TeamSerializer(latest_teams, many=True)

        return Response(serializer.data, status=200)

class TeamDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        team = Team.objects.get(id=team_id)
        serializer = TeamSerializer(team)
        return Response(serializer.data)

class TeamProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        projects = Project.objects.filter(team_id=team_id)
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)

class CreateProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, team_id):
        try:
            # Ensure the team exists and the user has permission
            team = Team.objects.get(id=team_id)
            print(team_id)
            # Validate and save the project data
            print("data: ", request.data)
            serializer = ProjectSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(team=team)  # Link the project to the team
                return Response(serializer.data, status=201)
            return Response(serializer.errors, status=400)
        except Team.DoesNotExist:
            return Response({"error": "Team not found."}, status=404)

class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id, is_active=True)
            serializer = ProjectSerializer(project)
            return Response(serializer.data, status=200)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=404)

class TestSuiteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, is_active=True)
        test_suites = TestSuite.objects.filter(project=project, is_active=True)
        serializer = TestSuiteSerializer(test_suites, many=True)
        return Response(serializer.data)

class CreateTestSuiteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, is_active=True)
        serializer = TestSuiteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project=project, is_active=True)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class TestSuiteTestCasesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, test_suite_id):
        test_suite = get_object_or_404(TestSuite, id=test_suite_id, is_active=True)
        test_cases = TestCase.objects.filter(suite=test_suite, is_active=True)
        serializer = TestCaseSerializer(test_cases, many=True)
        return Response(serializer.data)

@csrf_exempt
def test_cases(request):
    if request.method == 'POST':
        try:
            # Parsing the JSON request body
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            content = body.get('content', '')
            print("Content:", content)
            
            # Setting OpenAI client
            client = OpenAI()
            
            # Defining the function schema for function calling
            functions = [
                {
                    "type": "function",
                    "function":{
                        "name": "create_test_case",
                        "description": "Create a test case object from the given parameters, call this when asked to generate test cases!",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "test_case_description": {
                                    "type": "string",
                                    "description": "Description of the test case"
                                },
                                "preconditions": {
                                    "type": "string",
                                    "description": "Preconditions for the test case"
                                },
                                "test_steps": {
                                    "type": "string",
                                    "description": "Bullet points steps to perform in the test case"
                                },
                                "expected_results": {
                                    "type": "string",
                                    "description": "Expected results of the test case either bullet points or one line depending on the case"
                                },
                                "priority": {
                                    "type": "string",
                                    "description": "Expected results of the test case either bullet points or one line depending on the case"
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Expected results of the test case either bullet points or one line depending on the case"
                                },
                            },
                            "required": ["test_case_description", "preconditions", "test_steps", "expected_results"],
                            "additionalProperties": False,
                            "strict": True
                        }
                    }
                }
            ]
            
            # Creating the message 
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional test case generator. Professionals will ask you to generate test cases based on text/user stories or code"
                },
                {
                    "role": "user",
                    "content": f"Hi, can you generate for me a test case using the function create_test_case, based on this content inside tripple quotations? \"\"\" + {content} +\"\"\""
                }
            ]
            
            
            # Making the API call to OpenAI
            try:
                # print("Here1") # Debugging print
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=functions,
                )
                
                # print("Here") # Debugging print
            except Exception as openai_error:
                print("OpenAI API Error:", str(openai_error))
                return JsonResponse({'error': str(openai_error)}, status=500)
            
            # Extracting the assistant's message
            assistant_message = response.choices[0].message
            print("OpenAI response:", assistant_message)
            
            
            if assistant_message.tool_calls:
                # print("Here TOO") # Debugging print
                tool_call = assistant_message.tool_calls[0]
            
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as json_error:
                    print("JSON decode error:", str(json_error))
                    return JsonResponse({'error': 'Failed to parse function arguments'}, status=500)
                
                # Creating the test case object
                test_case = {
                    'test_case_description': arguments.get('test_case_description'),
                    'preconditions': arguments.get('preconditions'),
                    'test_steps': arguments.get('test_steps'),
                    'expected_results': arguments.get('expected_results'),
                }
                
                print("test_case:", test_case)
                return JsonResponse(test_case)
            else:
                print("No function_call in assistant_message")
                return JsonResponse({'error': 'No function call in response'}, status=500)
        except Exception as e:
            print("Exception occurred:", str(e))
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
class SaveTestCaseView(APIView):
    def post(self, request):
        serializer = TestCaseSerializer(data=request.data)
        if serializer.is_valid():
            test_case = serializer.save(created_by_profile=request.user.profile)  # Save and get the instance
            return Response(
                {
                    "message": "Test case saved successfully",
                    "test_case": TestCaseSerializer(test_case).data,  # Serialize the saved instance
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SaveTestStepsView(APIView):
    def post(self, request):
        serializer = TestStepBatchSerializer(data=request.data)
        print("")
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Test steps saved successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
