# BakeSmart Test Accounts for Demo

## How to create these accounts:
1. Register each account through the app normally
2. Then go to Firebase Console → Firestore → users collection
3. Update the role and other fields as shown below

| Role | Email | Password | Manual Firestore Changes Needed |
|---|---|---|---|
| Baker (Verified) | baker@bakesmart.com | Baker@123 | Set verificationStatus: verified, bakerIsVerified: true |
| Baker (Unverified) | newbaker@bakesmart.com | Baker@123 | No changes needed, default is unverified |
| Customer | customer@bakesmart.com | Customer@123 | No changes needed |
| Admin | admin@bakesmart.com | Admin@123 | Set role: admin |

## Test Data to Add After Account Creation:
### As Verified Baker:
- Add 3 ingredients: Flour (1000g), Sugar (500g), Butter (250g)
- Add 2 products: Chocolate Cake (PKR 800), Butter Cookies (PKR 350)
- Mark Butter Cookies as surplus at PKR 250

### As Customer:
- Browse products
- Place one order for Chocolate Cake
