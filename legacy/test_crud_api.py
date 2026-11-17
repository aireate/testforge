import pytest
from common.request_util import RequestUtil
from common.log_util import info, error

BASE_URL = "https://jsonplaceholder.typicode.com"


@pytest.fixture(scope="module")
def api():
    return RequestUtil(base_url=BASE_URL)


class TestPostCRUD:
    """帖子 CRUD 操作测试"""

    def test_create_post(self, api):
        info("测试：创建新帖子")
        payload = {
            "title": "TestForge 自动化测试",
            "body": "这是一个自动化测试框架的演示",
            "userId": 1
        }
        response = api.post("/posts", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert data["title"] == payload["title"]
        assert data["body"] == payload["body"]
        assert data["userId"] == payload["userId"]
        assert "id" in data
        info(f"创建成功，帖子 ID: {data['id']}")

    def test_read_post(self, api):
        info("测试：读取单个帖子")
        response = api.get("/posts/1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == 1
        assert "title" in data
        assert "body" in data
        assert data["userId"] == 1

    def test_list_posts(self, api):
        info("测试：获取帖子列表")
        response = api.get("/posts", params={"_limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        first_post = data[0]
        assert "id" in first_post
        assert "title" in first_post
        info(f"共获取到 {len(data)} 条帖子")

    def test_update_post(self, api):
        info("测试：更新帖子内容")
        update_data = {
            "id": 1,
            "title": "更新后的标题",
            "body": "更新后的内容",
            "userId": 1
        }
        response = api.put("/posts/1", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == update_data["title"]
        assert data["body"] == update_data["body"]

    def test_delete_post(self, api):
        info("测试：删除帖子")
        response = api.delete("/posts/1")
        assert response.status_code == 200


class TestUserBusinessLogic:
    """用户相关业务逻辑测试"""

    def test_user_complete_info(self, api):
        info("测试：获取用户完整信息并验证关键字段")
        response = api.get("/users/1")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ["id", "name", "username", "email", 
                          "address", "phone", "website", "company"]
        for field in required_fields:
            assert field in data, f"缺少必要字段: {field}"
        
        assert isinstance(data["address"], dict)
        assert "street" in data["address"]
        assert "city" in data["address"]
        assert "zipcode" in data["address"]
        
        assert isinstance(data["company"], dict)
        assert "name" in data["company"]

    def test_user_posts_relationship(self, api):
        info("测试：验证用户与帖子的关联关系")
        user_response = api.get("/users/1")
        assert user_response.status_code == 200
        user = user_response.json()
        
        posts_response = api.get(f"/users/{user['id']}/posts")
        assert posts_response.status_code == 200
        posts = posts_response.json()
        
        for post in posts:
            assert post["userId"] == user["id"]
        info(f"用户 {user['name']} 共有 {len(posts)} 篇帖子")

    def test_post_comments(self, api):
        info("测试：获取帖子的评论列表")
        post_id = 1
        response = api.get(f"/posts/{post_id}/comments")
        assert response.status_code == 200
        
        comments = response.json()
        assert len(comments) > 0
        
        for comment in comments:
            assert comment["postId"] == post_id
            assert "name" in comment
            assert "email" in comment
            assert "body" in comment
            
            assert "@" in comment["email"], f"邮箱格式错误: {comment['email']}"
