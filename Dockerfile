FROM python:3.13

ADD oumodulesbot /oumodulesbot
ADD poetry.lock pyproject.toml /

RUN pip install $(grep -E '^requires = \[.poetry.*\]$' pyproject.toml | cut -d'"' -f2)
RUN poetry install

CMD [ "poetry", "run", "python", "-m", "oumodulesbot.main" ]
