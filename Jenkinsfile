pipeline {
    agent any

    environment {
        PYTHONIOENCODING = 'UTF-8'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                dir('testforge') {
                    bat 'pip install -r requirements.txt'
                }
            }
        }

        stage('Run Tests') {
            steps {
                dir('testforge') {
                    bat 'pytest --alluredir=allure-results'
                }
            }
        }
    }

    post {
        always {
            dir('testforge') {
                allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]
            }
        }
    }
}
