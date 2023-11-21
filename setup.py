from setuptools import setup, find_packages

setup(
    name="alabamaEncoder",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "scenedetect",
        "tqdm",
        "celery",
        "redis",
        "psutil",
        "opencv-python",
        "optuna",
    ],
    entry_points="""
      [console_scripts]
      alabamaEncoder=alabamaEncode.__main__:main
      """,
)
