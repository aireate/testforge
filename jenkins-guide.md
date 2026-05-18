# Jenkins 配置步骤（Windows 环境）

## 目录
1. [Jenkins 安装](#1-jenkins-安装)
2. [Git 插件安装](#2-git-插件安装)
3. [Allure 插件安装](#3-allure-插件安装)
4. [配置 Python 环境](#4-配置-python-环境)
5. [配置 Allure Commandline](#5-配置-allure-commandline)
6. [GitHub SSH 配置](#6-github-ssh-配置)
7. [新建 Pipeline 项目](#7-新建-pipeline-项目)
8. [执行 Jenkinsfile](#8-执行-jenkinsfile)
9. [查看 Allure 报告](#9-查看-allure-报告)

---

## 1. Jenkins 安装

### 1.1 下载 Jenkins
- 访问：https://www.jenkins.io/download/
- 下载 Windows 安装包（.msi）或 `.war` 包

### 1.2 安装 Jenkins（使用 .war 包）
```powershell
# 下载 jenkins.war 后，在 cmd/PowerShell 中运行
java -jar jenkins.war --httpPort=8080

# 或后台运行（推荐）
Start-Process java -ArgumentList '-jar', 'jenkins.war', '--httpPort=8080' -NoNewWindow
```

### 1.3 初始化 Jenkins
- 打开浏览器访问：`http://localhost:8080`
- 按提示输入初始密码（查看控制台输出或 `C:\Users\<用户名>\.jenkins\secrets\initialAdminPassword`）
- 选择 **Install suggested plugins** 安装推荐插件
- 创建管理员账号 → 完成！

---

## 2. Git 插件安装

> 如果安装推荐插件时已安装 Git，可跳过此步。

### 2.1 检查并安装 Git 插件
1. 进入 **Manage Jenkins** → **Manage Plugins**
2. 点击 **Available** 标签
3. 搜索 `Git plugin`
4. 勾选 → 点击 **Install without restart**

### 2.2 配置 Git（可选）
1. **Manage Jenkins** → **Global Tool Configuration**
2. 找到 **Git**  section
3. 如果 Windows 已装 Git 且在 PATH 中，直接填 `git.exe`
4. 否则填完整路径：`C:\Program Files\Git\bin\git.exe`

---

## 3. Allure 插件安装

1. **Manage Jenkins** → **Manage Plugins** → **Available**
2. 搜索：`Allure Jenkins Plugin`
3. 勾选 → **Install without restart**

---

## 4. 配置 Python 环境

### 4.1 在 Jenkins Agent（本机）上安装 Python
- 下载：https://www.python.org/downloads/windows/
- 安装时 **务必勾选 "Add Python to PATH"**

### 4.2 验证 Python 在 Jenkins 可访问
在 Jenkins 中新建一个 "Freestyle project"，运行：
```bat
python --version
pip --version
```
如果能正常输出版本号 → 成功！

---

## 5. 配置 Allure Commandline

### 5.1 下载 Allure Commandline
- 访问：https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/
- 选版本（如 `2.27.0`）→ 下载 zip：`allure-commandline-2.27.0.zip`
- 解压到：`C:\allure-2.27.0`（或自定义路径）

### 5.2 在 Jenkins 配置 Allure
1. **Manage Jenkins** → **Global Tool Configuration**
2. 找到 **Allure Commandline** section
3. 点击 **Add Allure Commandline**
   - **Name**: `allure`（或留空默认）
   - **Install directory**: `C:\allure-2.27.0`
4. **Save** 保存！

---

## 6. GitHub SSH 配置（可选，推荐）

> 如果你用 HTTPS 且不介意输入 token/密码，可跳过此步，直接在 Pipeline 中用 HTTPS URL。

### 6.1 在 Windows 生成 SSH Key
```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
# 连续回车（默认路径、无密码）
# 公钥在：C:\Users\<你的用户名>\.ssh\id_ed25519.pub
```

### 6.2 把公钥加到 GitHub
1. 打开：https://github.com/settings/keys
2. **New SSH key**
3. Title 填：`Jenkins-Windows`
4. Key 内容粘贴刚才的 `id_ed25519.pub` 全部内容
5. **Add SSH key**

### 6.3 在 Jenkins 凭据中添加 SSH Private Key
1. **Manage Jenkins** → **Manage Credentials**
2. 选 **System** → **Global credentials (unrestricted)**
3. **Add Credential**
   - **Kind**: `SSH Username with private key`
   - **Username**: `git`
   - **Private Key**: Enter directly → 粘贴 `C:\Users\<你>\.ssh\id_ed25519` 私钥内容
   - **ID/Description**: 可选填
4. **Create**

---

## 7. 新建 Pipeline 项目

### 7.1 创建 Item
1. 回到 Jenkins 首页 → **New Item**
2. 输入名称：`TestForge-AutoTest`（自定）
3. 选 **Pipeline** → **OK**

### 7.2 Pipeline 配置
1. 找到 **Pipeline** section
2. **Definition**: 选 `Pipeline script from SCM`
3. **SCM**: 选 `Git`
4. **Repository URL**:
   - SSH 方式：`git@github.com:aireate/testforge.git`
   - HTTPS 方式：`https://github.com/aireate/testforge.git`
5. **Credentials** (如用 SSH)：选刚才建的 `git/SSH key` 那个凭据
6. **Script Path**: 保持默认：`Jenkinsfile`
7. **Save** 保存！

---

## 8. 执行 Jenkinsfile

### 8.1 立即构建
1. 在项目页（`TestForge-AutoTest`）点击 **Build Now**
2. 查看构建日志：
   - 点构建历史中最新的 #1 → **Console Output**
   - 观察日志确认：
     ```
     > Git checkout 成功
     > pip install -r requirements.txt 成功
     > pytest --alluredir=allure-results 执行（即使测试失败也会继续）
     > Allure report 已生成
     ```

---

## 9. 查看 Allure 报告

构建结束后，有两处入口：

### 入口 A：项目页
在 `TestForge-AutoTest` 项目页左侧菜单，点击 **Allure Report**

### 入口 B：构建详情页
点构建历史中某次构建 → 在详情页里点击 **Allure Report**

---

## 常见问题 & 排错（Windows）

| 问题现象 | 排查方向 |
|---------|---------|
| `pip 不是内部或外部命令` | 1. agent 上 Python 未装 / 不在 PATH<br>2. 重启 Jenkins agent/服务再试 |
| Allure 报告空白 / 中文乱码 | 确认 Jenkinsfile 中 environment 有 `PYTHONIOENCODING=UTF-8` |
| Git 连接超时/认证失败 | 1. Windows cmd 里先手动 git clone 下仓库，排障网络/凭据<br>2. 如用 SSH 先确认 `ssh -T git@github.com` 能通 |
| 报告里附件/截图乱码 | 系统层面把 Jenkins 启动参数也加上 UTF-8：<br>`java -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 -jar jenkins.war` |

---

## 项目文件回顾

| 文件 | 路径 |
|-----|------|
| Jenkinsfile | [Jenkinsfile](file:///d:/codecode/testforge/testforge/Jenkinsfile) |
| pytest 配置 | [pytest.ini](file:///d:/codecode/testforge/testforge/pytest.ini) |
| 依赖清单 | [requirements.txt](file:///d:/codecode/testforge/testforge/requirements.txt) |
| 测试用例 | [tests/test_demo.py](file:///d:/codecode/testforge/testforge/tests/test_demo.py) |
| 请求工具 | [common/request_util.py](file:///d:/codecode/testforge/testforge/common/request_util.py) |
