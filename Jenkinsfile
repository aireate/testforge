pipeline {
    agent any

    options {
        skipDefaultCheckout false
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

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
                bat 'pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    bat 'pytest --alluredir=allure-results'
                }
            }
        }
    }

    post {
        always {
            allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]
        }
        success {
            echo '✅ All tests passed!'
        }
        unstable {
            echo '⚠️ Some tests failed, please check the Allure report.'
        }
        failure {
            echo '❌ Pipeline failed.'
        }
    }
}
