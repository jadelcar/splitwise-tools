# Splitwise tools

Web app developed to expand the capabilities of Splitwise by leveraging its API.

## Batch upload
You can enter a set of expenses in a pre-defined excel template and submit these to your Splitwise account. 

Templates are particular to each group, and you can download these from the 'Group' tab once you have connected your Splitwise account through the 'Authorize' tab.

The template contains two sheets:
* ``Expenses``: Each row represents an expense, with columns for the attributes of the expense.
* ``Members``: Contains a list of the group members with their Splitwise ID. You may edit the names of members and their order for ease of use, as long as these match exactly the column names in sheet ``Expenses`` (regardless of order) and there are no duplicates.

The sheet ``Expenses`` contains the following columns:
  * **ID:** Defined by you, and only used for identifying expenses within this upload (must be unique within the excel file).
  * **Description:** Limited to 100 characters.
  * **Date:** Must follow the format DD/MM/YYYY.
  * **Amount:** Up to two decimal numbers.
  * **Currency:** Splitwise supports the following [currency codes](https://github.com/jadelcar/splitwise-tools/blob/3c9f5451bfe5e0db763b9336419e405cb9b944bd/static/assets/currencies.xlsx).
  * **Paid by:** Enter the name of the group member who has paid for this expense, exactly as written in the sheet ``Members``.
  * **All equal**: If you want this expense to be split equally among *all* the members of the group, enter 'Y'. The rest of columns to the right will be ignored). 
  * **Split type**: Enter one of the following keywords to indicate which method you will use to split the expenses.

    | **Keyword** 	| **Title** 	| **Description** 	|
    |---	|---	|---	|
    | ``Equal`` 	| Only some friends, split equally 	| Indicate which friends to include by entering 'X' in the corresponding column. The amount will be split equally among these members.|
    | ``Share`` 	| Split by share 	| Indicate the share (expressed as percentage, 0 to 100) assigned to each group member. Shares must add to 100. 	|
    | ``Amount`` 	| Split by amount 	| Indicate the exact amount assigned to each group member. Total must add up to the number under the column 'Amount' 	|
* **Friend columns**: 
  * There must be one column for each group member, matching the sheet ``Members``
  * Member names must be preceded by an underscore ('e.g. '_John').

## Expense review 
After uploading the file, this will be validated and you will see a summary of all expenses. Under each group member, the amount assigned to them will be displayed in parenthesis. Please review that these are the amounts you expected before clicking on 'upload'.

If there's any errors detected in the file, you will see a message at the top describing each error and the expenses affected. In some cases, these will be highlighted in the table. Please fix these and upload the expenses again.

## Future improvements:



