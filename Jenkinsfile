pipeline {
    agent any

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    triggers {
        // 每 15 分钟轮询一次代码变更；如需定时回归可再加 cron('H 2 * * *')
        pollSCM('H/15 * * * *')
    }

    environment {
        PYTHONIOENCODING = 'UTF-8'
        TESTFORGE_JWT_SECRET = 'jenkins-pipeline-secret-0123456789abcdef'
    }

    stages {
        stage('Test') {
            failFast true
            parallel {
                stage('接口测试') {
                    agent {
                        docker {
                            image 'python:3.11-slim'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'pip install --no-cache-dir -r requirements.txt'
                        sh 'python -m compileall -q sut common api config tests'
                        sh 'python -m pytest -m "not ui" -n 4 --alluredir=allure-results/api --junitxml=reports/api.xml'
                    }
                }

                stage('UI 测试') {
                    agent {
                        docker {
                            // 镜像内置 Chromium 与系统依赖，UI 用例使用 bundled 浏览器
                            image 'mcr.microsoft.com/playwright/python:v1.49.0-jammy'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'pip install --no-cache-dir -r requirements.txt'
                        withEnv(['TESTFORGE_BROWSER_CHANNEL=bundled']) {
                            sh 'python -m pytest -m ui --alluredir=allure-results/ui --junitxml=reports/ui.xml'
                        }
                    }
                }

                stage('冒烟测试') {
                    agent {
                        docker {
                            image 'python:3.11-slim'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'pip install --no-cache-dir -r requirements.txt'
                        sh 'python -m pytest -m smoke --alluredir=allure-results/smoke --junitxml=reports/smoke.xml'
                    }
                }

                stage('AI 归因评测') {
                    agent {
                        docker {
                            image 'python:3.11-slim'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'pip install --no-cache-dir -r requirements.txt'
                        // 准确率低于 80% 时返回非 0，阻止劣化合入
                        sh 'python tools/eval_triage.py --min-accuracy 0.8 --out reports/triage_eval.md'
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/*.xml'
            archiveArtifacts artifacts: 'reports/*.xml, reports/triage_eval.md', allowEmptyArchive: true
            allure includeProperties: false, jdk: '', results: [
                [path: 'allure-results/api'],
                [path: 'allure-results/ui'],
                [path: 'allure-results/smoke']
            ]
        }
        success {
            echo '全部测试通过，Allure 报告已归档。'
        }
        unstable {
            echo '存在失败用例，请查看 Allure 报告与 JUnit 结果。'
        }
        failure {
            echo '流水线执行失败。'
        }
    }
}
