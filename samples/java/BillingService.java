public class BillingService {

    // Main method - starting point of the program
    public static void main(String[] args) {

        BillingService billingService = new BillingService();

        System.out.println("================================");
        System.out.println("       BILLING SERVICE");
        System.out.println("================================");

        billingService.processBilling();

        System.out.println("================================");
        System.out.println("Billing process completed.");
    }

    // Main billing process
    public void processBilling() {

        System.out.println("\nStarting billing process...");

        // Validate the input
        boolean isValid = validateInput();

        if (!isValid) {
            System.out.println("Billing process stopped because input validation failed.");
            return;
        }

        // Calculate interest
        double interest = calcInterest();

        System.out.println("Interest calculated: " + interest);
        System.out.println("Billing processed successfully.");
    }

    // Validates billing input
    public boolean validateInput() {

        System.out.println("Validating billing input...");

        // Sample validation
        double billingAmount = 100.0;

        if (billingAmount <= 0) {
            raiseError();
            return false;
        }

        return true;
    }

    // Calculates interest
    public double calcInterest() {

        double billingAmount = 100.0;
        double interestRate = 0.05;

        return billingAmount * interestRate;
    }

    // Handles billing errors
    public void raiseError() {

        System.err.println("Billing error raised.");
    }
}