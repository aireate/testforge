import pytest
from common.request_util import RequestUtil
from common.log_util import info, error
import requests

BASE_URL = "https://jsonplaceholder.typicode.com"


@pytest.fixture(scope="module")
def api():
    return RequestUtil(base_url=BASE_URL)


class TestErrorScenarios:
    """错误与异常场景测试"""

    def test_get_nonexistent_user_404(self, api):
        info("测试：查询不存在的用户应返回 404")
        response = api.get("/users/99999")
        assert response.status_code == 404

    def test_get_nonexistent_post_404(self, api):
        info("测试：查询不存在的帖子应返回 404")
        response = api.get("/posts/99999")
        assert response.status_code == 404

    def test_post_without_body(self, api):
        info("测试：POST 请求不带 body 应返回 400 或创建空资源")
        response = api.post("/posts", json={})
        assert response.status_code in [201, 400, 422]

    def test_post_with_empty_title(self, api):
        info("测试：创建标题为空的帖子")
        payload = {"title": "", "body": "内容", "userId": 1}
        response = api.post("/posts", json=payload)
        assert response.status_code in [201, 400, 422]

    def test_put_to_nonexistent_resource(self, api):
        info("测试：更新不存在的资源")
        update_data = {"id": 99999, "title": "test", "body": "test"}
        response = api.put("/posts/99999", json=update_data)
        assert response.status_code in [200, 404, 500]

    def test_invalid_user_id_negative(self, api):
        info("测试：使用负数用户 ID")
        response = api.get("/users/-1")
        assert response.status_code != 200

    def test_invalid_user_id_string(self, api):
        info("测试：使用字符串作为用户 ID（类型错误）")
        try:
            response = api.get("/users/abc")
            if response.status_code == 200:
                data = response.json()
                assert data is not None
        except requests.exceptions.RequestException:
            pass


class TestDataValidation:
    """数据格式验证测试"""

    def test_email_format_valid(self, api):
        info("测试：验证用户邮箱格式正确")
        response = api.get("/users/1")
        data = response.json()
        
        email = data["email"]
        assert "@" in email, f"邮箱缺少 @ 符号: {email}"
        assert "." in email.split("@")[-1], f"邮箱域名格式错误: {email}"

    def test_user_address_complete(self, api):
        info("测试：验证用户地址信息完整")
        response = api.get("/users/2")
        data = response.json()
        
        address = data["address"]
        required_keys = ["street", "suite", "city", "zipcode"]
        for key in required_keys:
            assert key in address, f"地址缺少字段: {key}"
            assert address[key], f"地址字段 {key} 为空"

    def test_zipcode_format_us(self, api):
        info("测试：验证邮编格式（美式）")
        response = api.get("/users/1")
        data = response.json()
        zipcode = data["address"]["zipcode"]
        
        has_digits = any(c.isdigit() for c in zipcode)
        assert has_digits, f"邮编应该包含数字: {zipcode}"


class TestResponseTime:
    """响应时间性能测试"""

    @pytest.mark.parametrize("endpoint", ["/users/1", "/posts/1", "/comments/1"])
    def test_response_time_under_5s(self, api, endpoint):
        info(f"性能测试：{endpoint} 响应时间应在 5 秒内")
        response = api.get(endpoint)
        elapsed = response.elapsed.total_seconds()
        assert elapsed < 5.0, f"响应时间过长: {elapsed:.2f}s"
        info(f"{endpoint} 响应时间: {elapsed:.2f}s")


class TestResponseStructure:
    """响应结构一致性测试"""

    def test_all_users_have_same_structure(self, api):
        info("测试：所有用户应有相同的结构")
        response = api.get("/users?_limit=5")
        users = response.json()
        
        expected_fields = ["id", "name", "username", "email", 
                          "address", "phone", "website", "company"]
        
        for user in users:
            for field in expected_fields:
                assert field in user, f"用户 {user.get('id')} 缺少字段: {field}"

    def test_all_posts_have_same_structure(self, api):
        info("测试：所有帖子应有相同的结构")
        response = api.get("/posts?_limit=5")
        posts = response.json()
        
        expected_fields = ["id", "userId", "title", "body"]
        
        for post in posts:
            for field in expected_fields:
                assert field in post, f"帖子 {post.get('id')} 缺少字段: {field}"


@pytest.mark.xfail(reason="模拟已知缺陷，待修复")
class TestKnownDefects:
    """标记已知缺陷的测试用例"""

    def test_this_will_fail_intentionally(self, api):
        info("这是一个故意失败的测试，用于演示 xfail 标记")
        assert False, "这个测试预期失败，用于展示缺陷跟踪能力"
