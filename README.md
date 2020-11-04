Getting Started
-----------

### Install requirements
> #### Virtual environment setup

1. [__optional__] install Virtual Python Environment builder
    ```bash
    pip install virtualenv 
    ```
1. Create your virtual environment
    ```bash
    virtualenv -p python3 <environment_name>
    virtualenv -p python3 venv
    ```
1. Finally, activate it
    ```bash
    source ./venv/bin/activate
    ```

    > On activation, your terminal should now start with _(venv)_

1. Make sure lists are installed, python version is 3.8
    ```bash
    pip list
    python -V
    ```
> In a __virtual environment__ with _python 3.8_
    
```bash
    pip install -r requirements.txt
```
---

### Run
> Make sure the virtual environment is __activated__
```bash
python main.py
```
