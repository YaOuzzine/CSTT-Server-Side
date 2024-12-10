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
from .models import Team, TeamInvite, TeamMember, Profile, Project, TestSuite, TestCase, TestStep, TestData
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserRegistrationSerializer, UserLoginSerializer, TestCaseSerializer, TestStepBatchSerializer, TeamSerializer, ProjectSerializer, TestSuiteSerializer, TestStepSerializer


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
            client = OpenAI()
            
            # Handle multipart form data
            content = request.POST.get('content', '')
            project_description = request.POST.get('project_description', '')
            input_type = request.POST.get('input_type', 'text')
            image = request.FILES.get('image')
            
            # Prepare content based on input type
            if input_type == 'image' and image:
                # Convert image to base64 if needed
                import base64
                image_content = base64.b64encode(image.read()).decode('utf-8')
                content = f"[Image Description] This is an image upload. Please analyze this image and generate appropriate test cases."
                # Add image to the messages for vision model
                messages = [
                    {
                        "role": "system",
                        "content": "You are a professional test case generator. You will receive images or text content along with project descriptions to generate comprehensive test cases."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Project Context: {project_description}\n\nPlease generate test cases based on this image."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_content}"
                                }
                            }
                        ]
                    }
                ]
                
                print(messages)
                # Use GPT-4 Vision for image analysis
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=1000,
                )
                # Extract the response and feed it to the test case generation
                content = response.choices[0].message.content
            
            # Define function schema
            functions = [
                {
                    "type": "function",
                    "function": {
                        "name": "create_test_case",
                        "description": "Create a test case object from the given parameters",
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
                                    "description": "Expected results of the test case"
                                }
                            },
                            "required": ["test_case_description", "preconditions", "test_steps", "expected_results"]
                        }
                    }
                }
            ]
            
            # Create messages including project description
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional test case generator. Generate detailed test cases based on the provided content and project context."
                },
                {
                    "role": "user",
                    "content": f"""
                    Project Description:
                    {project_description}
                    
                    Content to generate test cases for:
                    {content}
                    
                    Please analyze both the project context and the provided content to generate comprehensive test cases."""
                }
            ]
            
            print(messages)
            # Make the API call to OpenAI for test case generation
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=functions,
                    tool_choice={"type": "function", "function": {"name": "create_test_case"}}
                )
            except Exception as openai_error:
                print("OpenAI API Error:", str(openai_error))
                return JsonResponse({'error': str(openai_error)}, status=500)
            
            # Extract the function call and arguments
            assistant_message = response.choices[0].message
            
            if assistant_message.tool_calls:
                tool_call = assistant_message.tool_calls[0]
                
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as json_error:
                    print("JSON decode error:", str(json_error))
                    return JsonResponse({'error': 'Failed to parse function arguments'}, status=500)
                
                # Create the test case object with generation source
                test_case = {
                    'test_case_description': arguments.get('test_case_description'),
                    'preconditions': arguments.get('preconditions'),
                    'test_steps': arguments.get('test_steps'),
                    'expected_results': arguments.get('expected_results'),
                    'generation_query': None,
                    'input_image_data': None,
                    'input_image_type': None
                }

                # Add the appropriate generation source based on input type
                if input_type == 'image' and image:
                    # Instead of saving the file, we'll pass the image data to the frontend
                    # This allows the frontend to handle the file upload when saving the test case
                    import base64
                    from django.core.files.base import ContentFile
                    
                    # Get the image data and type
                    image_data = base64.b64encode(image.read()).decode('utf-8')
                    image_type = image.content_type
                    
                    test_case['input_image_data'] = image_data
                    test_case['input_image_type'] = image_type
                else:
                    # Store the generation query (text or code)
                    test_case['generation_query'] = content
                
                print("Generated test case:", test_case)
                return JsonResponse(test_case)
            else:
                return JsonResponse({'error': 'No function call in response'}, status=500)
                
        except Exception as e:
            print("Exception occurred:", str(e))
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
class SaveTestCaseView(APIView):
    def post(self, request):
        try:
            # Extract image data if present
            input_image_data = request.data.get('input_image_data')
            input_image_type = request.data.get('input_image_type')
            
            print("Received data:")
            print("Image data length:", len(input_image_data) if input_image_data else 0)
            print("Image type:", input_image_type)
            print("Request data keys:", request.data.keys())
            
            # Create a copy of the data to modify
            test_case_data = request.data.copy()
            
            # Handle image data if present
            if input_image_data and input_image_type:
                import base64
                from django.core.files.base import ContentFile
                
                try:
                    # Convert base64 back to file
                    if isinstance(input_image_data, str):
                        # Handle potential prefixes
                        if ';base64,' in input_image_data:
                            # Split on ;base64, and take the second part
                            input_image_data = input_image_data.split(';base64,')[1]
                        
                        print("Attempting to decode base64 data...")
                        image_data = base64.b64decode(input_image_data)
                        print("Successfully decoded base64 data, length:", len(image_data))
                        
                        # Create a unique filename using UUID
                        import uuid
                        extension = input_image_type.split('/')[-1]
                        filename = f"{uuid.uuid4()}.{extension}"
                        
                        # Create a Django file object
                        image_file = ContentFile(image_data, name=filename)
                        
                        # Add the image file to the test case data
                        test_case_data['input_image'] = image_file
                        print(f"Created image file: {filename}")
                    else:
                        print("input_image_data is not a string:", type(input_image_data))
                except Exception as img_error:
                    print("Error processing image:", str(img_error))
                    raise
            
            print("Final test_case_data keys:", test_case_data.keys())
            serializer = TestCaseSerializer(data=test_case_data)
            
            if not serializer.is_valid():
                print("Serializer errors:", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the test case with the proper file handling
            test_case = serializer.save(created_by_profile=request.user.profile)
            print("Successfully saved test case with ID:", test_case.id)
            
            return Response(
                {
                    "message": "Test case saved successfully",
                    "test_case": TestCaseSerializer(test_case).data,
                },
                status=status.HTTP_201_CREATED,
            )
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            print("Error saving test case:", str(e))
            print(traceback.format_exc())
            return Response(
                {"error": "Failed to save test case", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SaveTestStepsView(APIView):
    def post(self, request):
        serializer = TestStepBatchSerializer(data=request.data)
        print("")
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Test steps saved successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class TestCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, test_case_id):
        """Get test case details"""
        try:
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            serializer = TestCaseSerializer(test_case)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class EditTestCaseView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, test_case_id):
        """Update test case details"""
        try:
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            serializer = TestCaseSerializer(
                test_case,
                data=request.data,
                partial=True  # Allow partial updates
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class BatchUpdateTestStepsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, test_case_id):
        """Get or update test steps for a test case"""
        try:
            # If no steps data provided, return current steps
            if not request.data:
                test_steps = TestStep.objects.filter(
                    test_case_id=test_case_id
                ).order_by('order_number')
                serializer = TestStepSerializer(test_steps, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Validate the test case exists
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            
            # Prepare steps data
            steps_data = request.data.get('steps', [])
            if not isinstance(steps_data, list):
                return Response(
                    {"error": "Steps data must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add test_case reference to each step
            for step in steps_data:
                step['test_case'] = test_case_id

            # Validate steps data
            serializer = TestStepBatchSerializer(data={'steps': steps_data})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Delete existing steps
            TestStep.objects.filter(test_case=test_case).delete()

            # Create new steps
            serializer.save()
            
            # Return updated steps
            test_steps = TestStep.objects.filter(
                test_case=test_case
            ).order_by('order_number')
            response_serializer = TestStepSerializer(test_steps, many=True)
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TestCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, test_case_id):
        """Get test case details"""
        try:
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            serializer = TestCaseSerializer(test_case)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class EditTestCaseView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, test_case_id):
        """Update test case details"""
        try:
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            print(test_case_id)
            serializer = TestCaseSerializer(
                test_case,
                data=request.data,
                partial=True  # Allow partial updates
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class BatchUpdateTestStepsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, test_case_id):
        """Get or update test steps for a test case"""
        try:
            # If no steps data provided, return current steps
            if not request.data:
                test_steps = TestStep.objects.filter(
                    test_case_id=test_case_id
                ).order_by('order_number')
                serializer = TestStepSerializer(test_steps, many=True)
                print("Returning steps: ", serializer.data)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Validate the test case exists
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            
            # Prepare steps data
            steps_data = request.data.get('steps', [])
            if not isinstance(steps_data, list):
                return Response(
                    {"error": "Steps data must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add test_case reference to each step
            for step in steps_data:
                step['test_case'] = test_case_id

            # Validate steps data
            serializer = TestStepBatchSerializer(data={'steps': steps_data})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Delete existing steps
            TestStep.objects.filter(test_case=test_case).delete()

            # Create new steps
            serializer.save()
            
            # Return updated steps
            test_steps = TestStep.objects.filter(
                test_case=test_case
            ).order_by('order_number')
            response_serializer = TestStepSerializer(test_steps, many=True)
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except TestCase.DoesNotExist:
            return Response(
                {"error": "Test case not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProjectTestCasesView(APIView):
    def get(self, request, project_id):
        """
        Get all test cases under all test suites for a specific project.
        """
        # Ensure the project exists
        project = get_object_or_404(Project, id=project_id, is_active=True)
        
        # Fetch all active test suites for the project
        test_suites = TestSuite.objects.filter(project=project, is_active=True)
        
        # Fetch all active test cases for the retrieved test suites
        test_cases = TestCase.objects.filter(suite__in=test_suites, is_active=True).select_related('suite', 'created_by_profile')
        
        # Serialize the test cases
        serializer = TestCaseSerializer(test_cases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class GenerateTemplateSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, test_case_id):
        try:
            # Fetch the test case and its steps
            test_case = get_object_or_404(TestCase, id=test_case_id, is_active=True)
            test_steps = TestStep.objects.filter(test_case=test_case).order_by('order_number')

            # Prepare the test steps string
            steps_text = ""
            for i, step in enumerate(test_steps):
                steps_text += f"{i+1}. Action: {step.action}\n   Expected Result: {step.expected_result}\n"

            # Prepare the content for OpenAI
            content = f"""Test Case Title: {test_case.title}
Description: {test_case.description}
Type: {test_case.type}

Test Steps:
{steps_text}"""

            client = OpenAI()

            # Define the function schema for field suggestions
            functions = [{
                "type": "function",
                "function": {
                    "name": "suggest_data_fields",
                    "description": "Suggest data fields based on test case analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fields": {
                                "type": "array",
                                "description": "Array of suggested data fields",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name of the field"
                                        },
                                        "type": {
                                            "type": "string",
                                            "description": "Data type of the field (string, number, boolean, date, etc.)"
                                        },
                                        "constraints": {
                                            "type": "string",
                                            "description": "Any constraints or validation rules for the field"
                                        }
                                    },
                                    "required": ["name", "type", "constraints"]
                                }
                            }
                        },
                        "required": ["fields"]
                    }
                }
            }]

            # Create messages for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert test data template generator. Analyze test cases and suggest appropriate "
                              "data fields that would be needed to support the test scenarios. Consider input data, validation rules, "
                              "and edge cases when suggesting fields."
                },
                {
                    "role": "user",
                    "content": f"Please analyze this test case and suggest appropriate data fields for generating test data:\n\n"
                              f"{content}\n\n"
                              f"Consider:\n"
                              f"1. Input fields mentioned in test steps\n"
                              f"2. Data needed for validations\n"
                              f"3. Common related fields that might be needed\n"
                              f"4. Appropriate data types and constraints"
                }
            ]

            # Make the API call to OpenAI
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=functions,
                    tool_choice={"type": "function", "function": {"name": "suggest_data_fields"}}
                )
            except Exception as openai_error:
                print("OpenAI API Error:", str(openai_error))
                return Response({'error': str(openai_error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Extract the function call and arguments
            assistant_message = response.choices[0].message

            if assistant_message.tool_calls:
                tool_call = assistant_message.tool_calls[0]
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    return Response(arguments)
                except json.JSONDecodeError as json_error:
                    print("JSON decode error:", str(json_error))
                    return Response(
                        {'error': 'Failed to parse suggestions'}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                return Response(
                    {'error': 'No suggestions generated'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            print("Exception occurred:", str(e))
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SaveTestDataView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            
            test_data = TestData.objects.create(
                name=data['name'],
                data_template=data['template'],
                format_type='json',
                created_by_profile=request.user.profile,
                is_active=True
            )
            
            # Link to test case if provided
            if data.get('testCaseId'):
                test_case = TestCase.objects.get(id=data['testCaseId'])
                test_data.test_cases.add(test_case)
            
            return Response({
                'message': 'Test data saved successfully',
                'id': test_data.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GenerateTestDataView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            template = request.data.get('template')
            test_case_id = request.data.get('testCaseId')
            
            # Get the test case for context
            test_case = get_object_or_404(TestCase, id=test_case_id)
            test_steps = TestStep.objects.filter(test_case=test_case).order_by('order_number')

            # Prepare the test steps for context
            steps_text = ""
            for i, step in enumerate(test_steps):
                steps_text += f"{i+1}. Action: {step.action}\n   Expected Result: {step.expected_result}\n"
            
            # Prepare the message with test case context
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a test data generator. Based on the provided test case and template, "
                        "generate sample test data in JSON format. The data should be realistic and "
                        "follow the specified field types and constraints."
                    )
                },
                {
                    "role": "user",
                    "content": f"""Please generate 5 sample test data records in JSON format based on:

Test Case:
Title: {test_case.title}
Description: {test_case.description}
Steps:
{steps_text}

Template Fields:
{json.dumps(template['fields'], indent=2)}

Requirements:
1. Generate exactly 5 records
2. Return data as a JSON array of objects
3. Each object should have all the specified fields
4. Follow the field types strictly
5. Data should be realistic and relevant to the test case
6. Return ONLY the JSON array, no explanation needed"""
                }
            ]

            client = OpenAI()
            
            # Call OpenAI API with explicit JSON format requirement
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={ "type": "json_object" },
                temperature=0.7
            )
            
            # Parse and validate the response
            try:
                generated_data = json.loads(response.choices[0].message.content)
                
                # Ensure we have a records array
                if 'records' not in generated_data:
                    # If we got a direct array, wrap it
                    if isinstance(generated_data, list):
                        generated_data = {'records': generated_data}
                    else:
                        # Create a records key if we got a single object
                        generated_data = {'records': [generated_data]}
                
                return Response(generated_data, status=status.HTTP_200_OK)
            
            except json.JSONDecodeError as e:
                print("JSON decode error:", str(e))
                return Response(
                    {'error': 'Failed to parse generated data'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            print("Error generating test data:", str(e))
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class TestDataListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            test_data = TestData.objects.filter(
                created_by_profile=request.user.profile,
                is_active=True
            ).order_by('-created_at')

            data = []
            for td in test_data:
                data.append({
                    'id': str(td.id),
                    'name': td.name,
                    'description': td.description,
                    'data_template': td.data_template,  # Changed from 'template'
                    'format_type': td.format_type,
                    'created_at': td.created_at,
                    'updated_at': td.updated_at,
                    'is_active': td.is_active,
                    'test_cases': [
                        {
                            'id': str(tc.id),
                            'title': tc.title
                        } for tc in td.test_cases.all()
                    ]
                })

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )