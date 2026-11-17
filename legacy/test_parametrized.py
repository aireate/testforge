import pytest
from common.request_util import RequestUtil
from common.log_util import info

BASE_URL = "https://jsonplaceholder.typicode.com"


@pytest.fixture(scope="module")
def api():
    return RequestUtil(base_url=BASE_URL)


class TestParametrizedUsers:
    """参数化用户查询测试"""

    @pytest.mark.parametrize("user_id", [1, 2, 3, 4, 5])
    def test_get_multiple_users(self, api, user_id):
        info(f"参数化测试：获取用户 {user_id} 的信息")
        response = api.get(f"/users/{user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == user_id
        assert "username" in data
        assert "email" in data

    @pytest.mark.parametrize("user_id,expected_username", [
        (1, "Bret"),
        (2, "Antonette"),
        (3, "Samantha"),
        (4, "Karianne"),
        (5, "Kamren"),
    ])
    def test_usernames_match_expected(self, api, user_id, expected_username):
        info(f"参数化测试：验证用户 {user_id} 的用户名")
        response = api.get(f"/users/{user_id}")
        data = response.json()
        assert data["username"] == expected_username


class TestParametrizedPosts:
    """参数化帖子操作测试"""

    test_post_data = [
        {
            "title": "Python 自动化测试入门",
            "body": "学习 pytest 和 requests",
            "userId": 1
        },
        {
            "title": "接口测试最佳实践",
            "body": "分层断言与数据驱动",
            "userId": 2
        },
        {
            "title": "CI/CD 流水线搭建",
            "body": "Jenkins + Allure 集成方案",
            "userId": 3
        },
    ]

    @pytest.mark.parametrize("post_data", test_post_data)
    def test_create_various_posts(self, api, post_data):
        info(f"参数化测试：创建帖子 - {post_data['title']}")
        response = api.post("/posts", json=post_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["title"] == post_data["title"]
        assert data["body"] == post_data["body"]
        assert data["userId"] == post_data["userId"]

    @pytest.mark.parametrize("post_id", [1, 2, 3])
    def test_posts_have_required_fields(self, api, post_id):
        info(f"参数化测试：验证帖子 {post_id} 的必要字段")
        response = api.get(f"/posts/{post_id}")
        data = response.json()
        
        required_fields = ["id", "title", "body", "userId"]
        for field in required_fields:
            assert field in data


class TestParametrizedEdgeCases:
    """边界值参数化测试"""

    @pytest.mark.parametrize("limit,count", [
        (1, 1),
        (5, 5),
        (10, 10),
    ])
    def test_list_with_limit(self, api, limit, count):
        info(f"参数化测试：限制返回数量为 {limit}")
        response = api.get("/posts", params={"_limit": limit})
        data = response.json()
        assert len(data) <= limit
