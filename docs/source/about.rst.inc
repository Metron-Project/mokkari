**mokkari** is a python wrapper for the Metron Comic Book Databaser API.

.. code-block:: python

    import mokkari

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