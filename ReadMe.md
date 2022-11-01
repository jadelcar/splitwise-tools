# Splitwise tools

Web app developed to expand the capabitilies of Splitwise by leveraging its API.

## Features
The app offers the following features at the moment:
* View your list of groups
* Batch upload

## Batch upload
The user enters a set of expenses in a pre-defined excel template and uploads this to the app, that automatically enters the expenses in Splitwise. 

The app supports the following  split methods:
* **All friends equally (default):** The expense is split equally among all the members in the group
* **Some friends equally**: User defines which users to include in the expense, and the amount is split equally. 
* **By share:** User defines the share (in percentage) that is assigned to each member
* **By amount:** User defines the exact amount to be assigned to  to upload a set of expenses entered into a pre-defined template.

The user must first authorize the app to log into their personal Spitwise account and choose the group to which the expenses must be uploaded.

## Registration and login
Using the app is quite simple, simply follow these steps
1. Register an account: Click on 'Register' and enter your preferred user name and password, and confirm your password. Now you can login to your personal account in the app.
2. Authorize Splitwise: Click on 'Authorize Splitwise', whcih will redirect you to the website's login screen. Enter your credentials and in the next screen select 'Authorize'. You will be redirected back to Splitwise tools, and all the apps features will be available to you. [As of 01/11/2022: You will need to authorize Splitwise every time that you access the app. This is done to protect your privacy and enhance the security of the app, given that at this stage this is simply a proof-of-concept].

## Uploading and reviewing expenses
Once in the batch upload screen, select the group to which you wish to upload the expenses, out of the groups where you are a member, and then select the file you wish to upload. Note that the structure and content of the file must be line with the group selected. 

The template must comply with the rules. If any of the expenses violates one or more rules, these will be described to the user. For more instructions on how to complete the template, continue reading.

### The template
Expenses uploaded must comply with this [template](link), which contains the following columns:
* **ID:** Defined by the user, but must be unique within the template, as it will help the user identify errors
* **Description:** Limited to 100 characters
* **Date:** Must follow the format DD/MM/YYYY
* **Amount:** Up to two decimal numbers
* **Currency:** Splitwise supports the following [currency codes](https://link-url-here.org)
* **Paid_by:** Enter the _first name of the user_ who has paid for this expense. To refer to yourself, enter 'You'.
* **All_equal**: Indicates if this expense will follow the default method of splitting equally among all members. Accepts 'y' or 'n'. If you select, 'y', the rest of columns will be ignored. Otherwise, you must complete the rest of columns to indicate how the expense needs to be split
* **Type_split**: Enter one of the following to indicate how the expenses must be divided: 'Share', 'Amount' or 'Equal'.
* **Friend columns**: 
  * There should be as many columns as members in the group to which you are planning to upload the expenses. 
  * Columns that refer to group members must have in the header the first name of the group member, preceded by an underscore (e.g. '_John'), except for the column that identifies the user uploading the expense, which is refered as 'you' (case insensitive).
  * The name appearing in the column header will be matched to the corresponding Splitwise user within the group with this first name (currently the app does not offer support for groups with members sharing their first name)


## Future improvemenets:
   * **Manual user validation of column to friend matching:** After the upload of expenses, the user can manually match each column to the correspoding group member, either accepting the automatic matching or selecting a different one. This procedure is in line with other web apps accepting files for uplaods, such as e-mail newsletter and contact management services. 
   * **Support for groups with members sharing a first name:**



## Review the expense



