import pytest

from cfncli.exceptions import (
    ApplicationException,
    handle_exceptions,
)
from cfncli.helpers import (
    convert_json_fields,
    generate_response,
    get_ssm_parameter,
    str_to_json,
)



def test_str_to_json_success():
    str_input = '{"key": "value"}'
    expected_output = {"key": "value"}
    assert str_to_json(str_input) == expected_output


def test_str_to_json_pass():
    str_input = "not a json string"
    assert str_to_json(str_input) == str_input


def test_convert_json_fields():
    item = {"json_field": '{"key": "value"}', "non_json_field": "test"}
    fields = ["json_field"]
    expected_output = {"json_field": {"key": "value"}, "non_json_field": "test"}
    assert convert_json_fields(item, fields) == expected_output


def test_generate_response():
    data = {"key": "value"}
    status_code = 200
    expected_output = {"statusCode": 200, "body": '{"key": "value"}'}
    assert generate_response(data, status_code) == expected_output


def test_handle_exceptions_success():
    @handle_exceptions(user_exceptions=[])
    def function_that_does_not_raise(event, context):
        return "success"

    event = {}
    context = {}
    assert function_that_does_not_raise(event, context) == "success"


def test_handle_exceptions_failure():
    @handle_exceptions(user_exceptions=[ApplicationException])
    def function_that_raises(event, context):
        raise ApplicationException("error")

    event = {}
    context = {}
    response = function_that_raises(event, context)
    assert response["statusCode"] == 500
    assert response["body"] == '{"message": "error"}'


# @pytest.mark.parametrize(
#     "user_attribute, expected_output",
#     [
#         ("prefix:username", "username"),  # Normal case
#         ("username", "ocloud-user"),  # No colon to split on
#         (None, "ocloud-user"),  # No user attribute
#     ],
# )

@pytest.fixture
def mock_ssm_client(mocker):
    mock_client = mocker.Mock()
    mocker.patch("cfncli.helpers.boto3.client", return_value=mock_client)
    return mock_client


test_data = [
    (  # Case 1
        {"Parameter": {"Value": "test_value"}},  # Mocked response from get_parameter
        None,  # Mocked exception (None means no exception)
        "test_value",  # Expected return value from get_ssm_parameter
    ),
    (  # Case 2
        None,
        ApplicationException("Parameter not found."),
        "Parameter not found.",  # Expected exception message
    ),
]

@pytest.mark.parametrize("ssm_response, ssm_exception, expected", test_data)
def test_get_ssm_parameter(mock_ssm_client, ssm_response, ssm_exception, expected):
    mock_ssm_client.get_parameter.return_value = ssm_response
    if ssm_exception:
        mock_ssm_client.get_parameter.side_effect = ssm_exception

    if ssm_exception:
        with pytest.raises(ApplicationException) as e:
            get_ssm_parameter("test_param_name")
        assert str(e.value) == expected
    else:
        result = get_ssm_parameter("test_param_name")
        assert result == expected
