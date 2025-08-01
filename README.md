# Nutripatrol

Open Food Facts moderation tool (WIP).

## Wikipage

- https://wiki.openfoodfacts.org/Moderation
- [Meeting minutes](https://docs.google.com/document/d/1B9Ci42kl_jrFt2hi3PiWW9tM9l6B1sI5kQMI9Zd6QS4/edit)

## Meeting

Valentin and Raphael are working on this tool. They meet weekly. Please ping them on Slack if you'd like to contribute.
We have more general quality meeting every month.

## Pre-Commit

This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:

```console
pre-commit run
```
## Developing

### Get the repository

1. Clone this repository :

```console
git clone https://github.com/openfoodfacts/nutripatrol.git
```

2. Open it

```console
cd nutripatrol
```

### Run with docker containers

Make docker containers

```console
make up
```

### Authentication for local dev

### To test with a global instance of Product Opener

In .env file uncomment the AUTH_SERVER_STATIC variable.
If you want to use a local Product Opener Instance, use `http://world.openfoodfacts.localhost`

Then connect to your Open Food Facts profile, copy the session cookie
and paste it in the body at this endpoint /set_session_cookie (you have a form at the /docs URI).
