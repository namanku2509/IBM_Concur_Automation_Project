# Sample receipt PDFs for end-to-end testing.
# Place 6 PDF files here before running test_pipeline.py:
#
#   hotel_marriott.pdf            — hotel bill (multi-night stay)
#   taxi_ola.pdf                  — Ola/Uber ride receipt
#   flight_indigo.pdf             — IndiGo e-ticket
#   meals_restaurant.pdf          — restaurant dinner bill
#   meals_conference.pdf          — conference registration fee
#   misc_pharmacy.pdf             — pharmacy bill (edge case: uncategorised)
#
# To generate test PDFs from text, install reportlab:
#   pip install reportlab
# then run:
#   python data/generate_sample_pdfs.py
