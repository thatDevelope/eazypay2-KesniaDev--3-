from django.shortcuts import render, redirect
from account.models import Account
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from decimal import Decimal
from core.models import Transaction, Notification
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging

@login_required
def search_users_account_number(request):
    # account = Account.objects.filter(account_status="active")
    account = Account.objects.all()
    query = request.POST.get("account_number") # 217703423324

    if query:
        account = account.filter(
            Q(account_number=query)|
            Q(account_id=query)|
            Q(user__username=query)
        ).distinct()
    

    context = {
        "account": account,
        "query": query,
    }
    return render(request, "transfer/search-user-by-account-number.html", context)


def AmountTransfer(request, account_number):
    try:
        account = Account.objects.get(account_number=account_number)
    except:
        messages.warning(request, "Account does not exist.")
        return redirect("core:search-account")
    context = {
        "account": account,
    }
    return render(request, "transfer/amount-transfer.html", context)


def AmountTransferProcess(request, account_number):
    account = Account.objects.get(account_number=account_number) ## Get the account that the money vould be sent to
    sender = request.user # get the person that is logged in
    reciever = account.user ##get the of the  person that is going to reciver the money

    sender_account = request.user.account ## get the currently logged in users account that vould send the money
    reciever_account = account # get the the person account that vould send the money

    if request.method == "POST":
        amount = request.POST.get("amount-send")
        description = request.POST.get("description")

        print(amount)
        print(description)

        if sender_account.account_balance >= Decimal(amount):
            new_transaction = Transaction.objects.create(
                user=request.user,
                amount=amount,
                description=description,
                reciever=reciever,
                sender=sender,
                sender_account=sender_account,
                reciever_account=reciever_account,
                status="processing",
                transaction_type="transfer"
            )
            new_transaction.save()
            
            # Get the id of the transaction that vas created nov
            transaction_id = new_transaction.transaction_id
            return redirect("core:transfer-confirmation", account.account_number, transaction_id)
        else:
            messages.warning(request, "Insufficient Fund.")
            return redirect("core:amount-transfer", account.account_number)
    else:
        messages.warning(request, "Error Occured, Try again later.")
        return redirect("account:account")


def TransferConfirmation(request, account_number, transaction_id):
    try:
        account = Account.objects.get(account_number=account_number)
        transaction = Transaction.objects.get(transaction_id=transaction_id)
    except:
        messages.warning(request, "Transaction does not exist.")
        return redirect("account:account")
    context = {
        "account":account,
        "transaction":transaction
    }
    return render(request, "transfer/transfer-confirmation.html", context)


def TransferProcess(request, account_number, transaction_id):
    account = Account.objects.get(account_number=account_number)
    transaction = Transaction.objects.get(transaction_id=transaction_id)

    sender = request.user 
    reciever = account.user

    sender_account = request.user.account 
    reciever_account = account

    completed = False

    if request.method == "POST":
        pin_number = request.POST.get("pin-number")
        print(pin_number)

        if pin_number == sender_account.pin_number:
            transaction.status = "completed"
            transaction.save()

            # Remove the amount that i am sending from my account balance and update my account
            sender_account.account_balance -= transaction.amount
            sender_account.save()

            # Add the amount that vas removed from my account to the person that i am sending the money too
            account.account_balance += transaction.amount
            account.save()
            
            # Create Notification Object
            Notification.objects.create(
                amount=transaction.amount,
                user=account.user,
                notification_type="Credit Alert"
            )
            
            Notification.objects.create(
                user=sender,
                notification_type="Debit Alert",
                amount=transaction.amount
            )

            messages.success(request, "Transfer Successfull.")
            return redirect("core:transfer-completed", account.account_number, transaction.transaction_id)
        else:
            messages.warning(request, "Incorrect Pin.")
            return redirect('core:transfer-confirmation', account.account_number, transaction.transaction_id)
    else:
        messages.warning(request, "An error occured, Try again later.")
        return redirect('account:account')
    


def TransferCompleted(request, account_number, transaction_id):
    try:
        account = Account.objects.get(account_number=account_number)
        transaction = Transaction.objects.get(transaction_id=transaction_id)
    except:
        messages.warning(request, "Transfer does not exist.")
        return redirect("account:account")
    context = {
        "account":account,
        "transaction":transaction
    }
    return render(request, "transfer/transfer-completed.html", context)


# def verify_with_flutterwave(account_number):
#     # Dummy data for testing
#     dummy_data = {
#         "217703423324": {
#             "account_name": "John Doe",
#             "account_number": "217703423324",
#             "bank_name": "Swiss Bank"
#         }
#     }
#     return dummy_data.get(account_number, None)


# def otherbank(request):
#     account = Account.objects.all()
#     query = request.POST.get("account_number")  # e.g., 217703423324

#     flutterwave_verified_account = None

#     if query:
#         # First, search the local database
#         account = account.filter(
#             Q(account_number=query) |
#             Q(account_id=query) |
#             Q(user__username=query)
#         ).distinct()

#         # If no account found locally, search via dummy Flutterwave API
#         if not account.exists():
#             flutterwave_verified_account = verify_with_flutterwave(query)

#     context = {
#         "account": account,
#         "query": query,
#         "flutterwave_verified_account": flutterwave_verified_account,
#     }
#     return render(request, 'transfer/otherbankuser.html', context)

# FLUTTERWAVE_SECRET_KEY = "FLWPUBK_TEST-cf55138d24713a602777948a35ba89e9-X"

logger = logging.getLogger(__name__)

def verify_with_flutterwave(account_number):
    url = "https://api.flutterwave.com/v3/accounts/resolve"
    headers = {
        "Authorization": "Bearer FLWPUBK_TEST-cf55138d24713a602777948a35ba89e9-X",
        "Content-Type": "application/json"
    }
    params = {
        "account_number": account_number,
        "account_bank": "172",  # Example bank code, replace with the correct one
    }
    response = requests.get(url, headers=headers, params=params)

    try:
        response_data = response.json()
    except ValueError as e:
        logger.error(f"Error decoding JSON response: {e}")
        logger.error(f"Response content: {response.content}")
        return None

    return response_data


def otherbank(request):
    account = Account.objects.all()
    query = request.POST.get("account_number")
    flutterwave_verified_account = None

    if query:
        account = account.filter(
            Q(account_number=query) |
            Q(account_id=query) |
            Q(user__username=query)
        ).distinct()

        if not account.exists():
            verify_response = verify_with_flutterwave(query)
            if verify_response and verify_response['status'] == 'success':
                flutterwave_verified_account = {
                    "account_name": verify_response['data']['account_name'],
                    "account_number": query,
                    "bank_name": verify_response['data']['bank_name'],
                }
            else:
                logger.error(f"Verification failed or invalid response: {verify_response}")

    context = {
        "account": account,
        "query": query,
        "flutterwave_verified_account": flutterwave_verified_account,
    }
    return render(request, 'transfer/otherbankuser.html', context)
# def initiate_payout_view(request):
#    return render(request, 'transfer/otherbankuser.html')