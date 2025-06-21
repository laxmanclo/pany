# Contributing to Pany

We love your input! We want to make contributing to Pany as easy and transparent as possible.

## Development Process

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Ensure the demo still works (`docker-compose up -d`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Local Development

```bash
# Clone the repo
git clone https://github.com/your-username/pany.git
cd pany

# Start the services
docker-compose up -d

# Test the demo
curl -X POST http://localhost:8000/setup-demo
open http://localhost:8000/demo
```

## Code Style

- Use Black for Python formatting
- Follow PEP 8 conventions
- Add type hints for new functions
- Write docstrings for public APIs

## Testing

```bash
# Run the test suite
python -m pytest tests/

# Test the API manually
python examples/test_api.py
```

## Issues

Feel free to submit issues for:
- Bug reports
- Feature requests
- Documentation improvements
- Performance suggestions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
