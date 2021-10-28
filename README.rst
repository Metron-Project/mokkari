=======
Mokkari
=======
.. image:: https://img.shields.io/pypi/v/mokkari.svg?logo=PyPI&label=Version&style=flat-square   :alt: PyPI
    :target: https://pypi.org/project/mokkari

.. image:: https://img.shields.io/pypi/pyversions/mokkari.svg?logo=Python&label=Python-Versions&style=flat-square
    :target: https://pypi.org/project/mokkari

.. image:: https://img.shields.io/github/license/bpepple/mokkari
    :target: https://opensource.org/licenses/GPL-3.0

.. image:: https://codecov.io/gh/bpepple/mokkari/branch/main/graph/badge.svg?token=QU1ROMMOS4
    :target: https://codecov.io/gh/bpepple/mokkari

.. image:: https://img.shields.io/badge/Code%20Style-Black-000000.svg?style=flat-square
    :target: https://github.com/psf/black

Quick Description
-----------------
A python wrapper for the metron.cloud_ API.

.. _metron.cloud: https://metron.cloud

Installation
------------

PyPi
~~~~

.. code:: bash

  $ pip3 install --user mokkari

Example Usage
-------------
.. code-block:: python

    import mokkari

    # Your own config file to keep your credentials secret
    from config import username, password

    m = mokkari.api(username, password)

    # Get all Marvel comics for the week of 2021-06-07
    this_week = m.issues_list({"store_date_range_after": "2021-06-07", "store_date_range_before": "2021-06-13", "publisher_name": "marvel"})

    # Print the results
    for i in this_week:
        print(f"{i.id} {i.issue_name}")

    # Retrieve the detail for an individual issue
    asm_68 = m.issue(31660)

    # Print the issue Description
    print(asm_68.desc)
  
Documentation
-------------
- `Read the project documentation <https://mokkari.readthedocs.io/en/latest/>`_

Bugs/Requests
-------------
  
Please use the `GitHub issue tracker <https://github.com/bpepple/mokkari/issues>`_ to submit bugs or request features.

License
-------

This project is licensed under the `GPLv3 License <LICENSE>`_.
