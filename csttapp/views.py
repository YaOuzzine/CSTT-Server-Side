from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import os
import json
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .serializers import UserRegistrationSerializer, UserLoginSerializer


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
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
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            # Get user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'error': 'Invalid email or password'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Authenticate using username (email) and password
            user = authenticate(username=user.username, password=password)
            
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
                                    "description": "Expected results of the test case"
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

