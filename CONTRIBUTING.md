# 🤝 Contributing to Medical Fake News Detection System

Thank you for your interest in contributing to this project! This guide will help you get started.

## 🎓 About This Project

This is a university thesis project focused on detecting medical misinformation on social media platforms using advanced NLP and AI techniques. While it's primarily an academic project, contributions are welcome and appreciated.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- MongoDB 4.4+
- Docker (optional but recommended)

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/medical-fake-news-detection.git
   cd medical-fake-news-detection
   ```

2. **Backend setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Frontend setup**
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Database setup**
   ```bash
   # Start MongoDB (or use Docker)
   docker run -d -p 27017:27017 --name mongodb mongo:7.0
   ```

5. **Run tests**
   ```bash
   # Backend tests
   cd backend && pytest
   
   # Frontend tests
   cd frontend && npm test
   ```

## 📋 How to Contribute

### 1. Issues
- Check existing issues before creating new ones
- Use appropriate issue templates
- Provide detailed information and steps to reproduce bugs
- Label issues appropriately

### 2. Pull Requests
- Create a feature branch from `main`
- Use descriptive branch names: `feature/add-sentiment-analysis` or `fix/authentication-bug`
- Make sure your code follows our style guidelines
- Include tests for new functionality
- Update documentation as needed
- Use the PR template and fill it out completely

### 3. Code Style

#### Python (Backend)
- Follow PEP 8
- Use Black for formatting: `black app/ tests/`
- Use isort for imports: `isort app/ tests/`
- Use type hints where appropriate
- Maximum line length: 88 characters

#### JavaScript/React (Frontend)
- Use Prettier for formatting
- Follow ESLint rules
- Use meaningful component and variable names
- Prefer functional components with hooks

#### Commit Messages
Follow the Conventional Commits specification:
```
feat: add sentiment analysis to post evaluation
fix: resolve authentication token expiration issue
docs: update API documentation for campaigns endpoint
test: add unit tests for auth service
refactor: optimize database query performance
```

### 4. Testing Guidelines

#### Backend Testing
- Write unit tests for all new functions
- Use pytest fixtures for test data
- Mock external API calls
- Aim for >80% code coverage
- Test both success and failure scenarios

```python
def test_register_user_success(app, mock_mongo_manager, sample_user_data):
    """Test successful user registration"""
    # Test implementation
```

#### Frontend Testing
- Write tests for all components
- Use React Testing Library
- Test user interactions
- Mock API calls

```javascript
test('renders login form correctly', () => {
  render(<LoginPage />);
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
});
```

### 5. Documentation

- Update README.md if needed
- Document new API endpoints
- Add inline code comments for complex logic
- Update configuration examples

## 🔍 Code Review Process

1. **Automated Checks**: All PRs run through CI/CD pipeline
2. **Manual Review**: Code will be reviewed for:
   - Functionality and correctness
   - Code quality and maintainability
   - Test coverage
   - Security considerations
   - Performance implications

3. **Approval**: PRs need approval before merging

## 🎯 Areas for Contribution

### High Priority
- [ ] Improve test coverage (backend and frontend)
- [ ] Add more LLM provider integrations
- [ ] Enhance social media data collection
- [ ] Optimize analysis performance
- [ ] Improve UI/UX design

### Medium Priority
- [ ] Add real-time notifications
- [ ] Implement advanced analytics
- [ ] Add more visualization options
- [ ] Improve Docker setup
- [ ] Add API rate limiting

### Documentation
- [ ] API documentation improvements
- [ ] User guide creation
- [ ] Architecture documentation
- [ ] Deployment guides

## 🐛 Bug Reports

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, browser, versions)
- Screenshots if applicable
- Error logs if available

## 💡 Feature Requests

For new features, please:
- Check if similar feature exists
- Explain the use case and motivation
- Describe the proposed solution
- Consider backwards compatibility
- Discuss implementation approach

## 🎓 Academic Considerations

This project is part of a university thesis, so please:
- Respect academic integrity guidelines
- Understand that major architectural changes may need thesis advisor approval
- Be patient with response times during exam periods
- Consider the academic timeline when proposing features

## 📞 Getting Help

- **Issues**: Use GitHub issues for bug reports and feature requests
- **Discussions**: Use GitHub discussions for questions and general discussion
- **Email**: Contact the maintainer for urgent matters or academic-related questions

## 🏆 Recognition

Contributors will be acknowledged in:
- GitHub contributors list
- Project documentation
- Thesis acknowledgments (with permission)

## 📜 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain a professional environment

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to the Medical Fake News Detection System! 🚀

*For questions about this contributing guide, please open an issue.*