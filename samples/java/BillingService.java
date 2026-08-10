package com.example.billing;

public class BillingService {

    public void processBilling() {
        validateInput();
        calcInterest();
    }

    public boolean validateInput() {
        raiseError();
        return false;
    }

    public double calcInterest() {
        return 100.0 * 0.05;
    }

    public void raiseError() {
        System.err.println("Billing error raised");
    }
}
