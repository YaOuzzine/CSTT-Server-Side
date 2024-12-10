from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Profile, TestCase, TestSuite, TestCase, TestStep, Team, Project

class UserRegistrationSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('full_name', 'email', 'password', 'confirm_password', 'role')

    def validate(self, attrs):
        if 'confirm_password' not in attrs:
            raise serializers.ValidationError({"confirm_password": "This field is required."})
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})
        
        return attrs

    def create(self, validated_data):
        full_name = validated_data['full_name'].split(' ', 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ''

        user = User.objects.create(
            username=validated_data['email'],  # Using email as username
            email=validated_data['email'],
            first_name=first_name,
            last_name=last_name
        )

        user.set_password(validated_data['password'])
        user.save()

        # Create associated profile
        Profile.objects.create(
            auth_user=user,
            role=validated_data['role']
        )

        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'description']

class NestedTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name"]

class ProjectSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "status",
            "is_active",
            "team",
        ]
        read_only_fields = ["id", "created_at", "team"]

    def validate_status(self, value):
        allowed_statuses = ["Pending", "In Progress", "Completed"]
        if value not in allowed_statuses:
            raise serializers.ValidationError(f"Status must be one of {allowed_statuses}.")
        return value

class TestSuiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = ['id', 'name', 'description', 'created_at', 'is_active']
        
class TestStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestStep
        fields = ['test_case', 'order_number', 'action', 'expected_result']

class TestCaseSerializer(serializers.ModelSerializer):
    steps = TestStepSerializer(many=True, required=False)
    suite = serializers.PrimaryKeyRelatedField(queryset=TestSuite.objects.all())

    class Meta:
        model = TestCase
        fields = ['id', 'title', 'description', 'priority', 'type', 
                  'status', 'suite', 'metadata', 'steps', "is_active", "generation_query", "input_image", "created_at", "updated_at", "created_by_profile"]
        read_only_fields = ['id']
        
    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        test_case = TestCase.objects.create(**validated_data)
        for step_data in steps_data:
            TestStep.objects.create(test_case=test_case, **step_data)
        return test_case

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', [])
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.priority = validated_data.get('priority', instance.priority)
        instance.type = validated_data.get('type', instance.type)
        instance.status = validated_data.get('status', instance.status)
        instance.suite = validated_data.get('suite', instance.suite)
        instance.metadata = validated_data.get('metadata', instance.metadata)
        instance.save()

        # Handle steps update
        if steps_data:
            instance.steps.all().delete()  # Delete old steps
            for step_data in steps_data:
                TestStep.objects.create(test_case=instance, **step_data)

        return instance


class TestStepBatchSerializer(serializers.Serializer):
    steps = TestStepSerializer(many=True)

    def validate_steps(self, value):
        if not value:
            raise serializers.ValidationError("Steps list cannot be empty.")
        return value

    def create(self, validated_data):
        steps_data = validated_data.get('steps')
        steps = [TestStep(**step_data) for step_data in steps_data]
        created_steps = TestStep.objects.bulk_create(steps)
        return {'steps': created_steps}

