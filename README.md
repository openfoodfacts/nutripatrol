# Nutripatrol

Open Food Facts moderation tool (WIP).

### Wikipage 
- https://wiki.openfoodfacts.org/Moderation
- [Meeting minutes](https://docs.google.com/document/d/1B9Ci42kl_jrFt2hi3PiWW9tM9l6B1sI5kQMI9Zd6QS4/edit)

### Meeting
Valentin and Raphael are working on this tool. They meet weekly. Please ping them on Slack if you'd like to contribute. 
We have more general quality meeting every month.

### Pre-Commit
This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:
```console
pre-commit run
```

### Get started
1. Clone this repository :
```console
git clone https://github.com/openfoodfacts/nutripatrol.git
```

2. Open it
```console
cd nutripatrol
```

3. Make docker containers
```console
make up
```

4. Install virtual environment python
```console
python3 -m venv venv
```

5. Activate it 
```console
# MacOS or Linux
source venv/bin/activate

# Windows
venv/Scripts/activate
```

6. Install requirement.txt dependencies
```console
pip3 install -r requirements.txt
```