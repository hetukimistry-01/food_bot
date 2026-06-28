"""
Script to generate the restaurant menu PDF.
Run once to create data/menu.pdf before starting the app.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

os.makedirs("data", exist_ok=True)

doc = SimpleDocTemplate(
    "data/menu.pdf",
    pagesize=A4,
    rightMargin=2*cm,
    leftMargin=2*cm,
    topMargin=2*cm,
    bottomMargin=2*cm,
)

styles = getSampleStyleSheet()
title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=28, textColor=colors.HexColor("#B5451B"), spaceAfter=4, alignment=TA_CENTER)
sub_style  = ParagraphStyle("Sub",   parent=styles["Normal"], fontSize=12, textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=16)
sec_style  = ParagraphStyle("Sec",   parent=styles["Heading2"], fontSize=15, textColor=colors.HexColor("#B5451B"), spaceBefore=18, spaceAfter=6)
item_style = ParagraphStyle("Item",  parent=styles["Normal"], fontSize=11, leading=15)
note_style = ParagraphStyle("Note",  parent=styles["Normal"], fontSize=9, textColor=colors.grey, spaceAfter=4)

MENU = {
    "🍔 Burgers": [
        ("Classic Veg Burger", "₹149", "Crispy vegetable patty, lettuce, tomato, onion, cheese, and burger sauce."),
        ("Paneer Tikka Burger", "₹199", "Grilled paneer tikka, mint mayo, onion rings, and fresh lettuce."),
        ("Aloo Tikki Burger", "₹139", "Spiced potato tikki with tomato, onion, and tangy chutney."),
        ("Cheese Burst Burger", "₹219", "Double cheese, crispy veg patty, jalapeños, and chipotle mayo."),
        ("Mexican Veg Burger", "₹209", "Veg patty topped with salsa, cheese, jalapeños, and lettuce."),
    ],

    "🍕 Pizzas": [
        ("Margherita Pizza", "₹249", "Classic mozzarella cheese with fresh tomato sauce."),
        ("Farmhouse Pizza", "₹329", "Capsicum, onion, tomato, mushrooms, and sweet corn."),
        ("Paneer Tikka Pizza", "₹359", "Paneer tikka, onions, capsicum, mozzarella, and spicy sauce."),
        ("Veggie Supreme Pizza", "₹349", "Loaded with fresh vegetables and mozzarella cheese."),
        ("Cheese Burst Pizza", "₹389", "Extra cheese-filled crust with mozzarella topping."),
    ],

    "🍝 Pasta": [
        ("White Sauce Pasta", "₹249", "Creamy Alfredo pasta with vegetables and herbs."),
        ("Red Sauce Pasta", "₹239", "Tomato basil sauce with garlic and mixed vegetables."),
        ("Pink Sauce Pasta", "₹259", "Perfect blend of creamy white and tangy red sauce."),
        ("Pesto Pasta", "₹279", "Fresh basil pesto tossed with penne pasta and vegetables."),
        ("Cheesy Baked Pasta", "₹299", "Oven-baked pasta topped with mozzarella cheese."),
    ],

    "🍚 Rice & Indian Meals": [
        ("Veg Biryani", "₹279", "Fragrant basmati rice cooked with vegetables and aromatic spices."),
        ("Paneer Biryani", "₹319", "Rich paneer biryani served with raita."),
        ("Jeera Rice", "₹149", "Basmati rice tempered with cumin and ghee."),
        ("Veg Pulao", "₹219", "Mildly spiced rice with seasonal vegetables."),
        ("Dal Khichdi", "₹199", "Comforting rice and lentils served with papad and pickle."),
    ],

    "🥘 Pav Bhaji & Street Food": [
        ("Classic Pav Bhaji", "₹179", "Mumbai-style buttery bhaji served with toasted pav."),
        ("Cheese Pav Bhaji", "₹229", "Classic pav bhaji topped with grated cheese."),
        ("Jain Pav Bhaji", "₹199", "Prepared without onion and garlic."),
        ("Extra Butter Pav Bhaji", "₹219", "Loaded with Amul butter for rich flavor."),
        ("Tawa Pulao", "₹229", "Mumbai street-style spicy pulao served with raita."),
    ],

    "🥗 Starters & Sides": [
        ("French Fries", "₹129", "Golden crispy fries with seasoning."),
        ("Peri Peri Fries", "₹149", "French fries tossed in spicy peri peri seasoning."),
        ("Cheese Garlic Bread", "₹179", "Toasted garlic bread topped with mozzarella."),
        ("Veg Spring Rolls", "₹199", "Crispy rolls stuffed with vegetables."),
        ("Paneer Tikka", "₹299", "Char-grilled paneer cubes with Indian spices."),
        ("Hara Bhara Kabab", "₹229", "Spinach and green pea patties served with mint chutney."),
    ],

    "🥤 Drinks": [
        ("Fresh Lime Soda", "₹89", "Sweet, salted, or mixed fresh lime soda."),
        ("Cold Coffee", "₹169", "Chilled coffee blended with milk and ice cream."),
        ("Mango Shake", "₹179", "Fresh mango milkshake."),
        ("Chocolate Shake", "₹189", "Rich chocolate milkshake topped with chocolate syrup."),
        ("Oreo Shake", "₹199", "Creamy Oreo cookie milkshake."),
        ("Masala Chaas", "₹79", "Refreshing spiced buttermilk."),
        ("Mineral Water", "₹30", "Packaged drinking water."),
        ("Soft Drinks", "₹60", "Coke, Sprite, Fanta, Thums Up, or Limca."),
    ],

    "🍨 Desserts": [
        ("Gulab Jamun (2 pcs)", "₹99", "Soft milk dumplings soaked in sugar syrup."),
        ("Brownie with Ice Cream", "₹199", "Warm chocolate brownie served with vanilla ice cream."),
        ("Chocolate Lava Cake", "₹179", "Molten chocolate cake served warm."),
        ("Kulfi", "₹119", "Traditional Indian frozen dessert."),
        ("Falooda", "₹199", "Rose-flavored falooda with ice cream and dry fruits."),
        ("Ice Cream Sundae", "₹169", "Vanilla ice cream topped with chocolate sauce and nuts."),
    ],
}

story = []
story.append(Paragraph("🍴 The Flame & Fork", title_style))
story.append(Paragraph("Fresh · Fast · Flavourful", sub_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#B5451B")))
story.append(Spacer(1, 10))
story.append(Paragraph(
    "Welcome! Every dish is made to order with quality ingredients.",
    note_style
))

for section, items in MENU.items():
    story.append(Paragraph(section, sec_style))
    table_data = [["Item", "Price", "Description"]]
    for name, price, desc in items:
        table_data.append([name, price, desc])
    t = Table(table_data, colWidths=[4.5*cm, 1.8*cm, 10.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#B5451B")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF8F5"), colors.white]),
        ("FONTSIZE",     (0, 1), (-1, -1), 9),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#E0C8BF")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(t)

story.append(Spacer(1, 20))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#B5451B")))
story.append(Paragraph("Thank you for dining with us!", note_style))

doc.build(story)
print("data/menu.pdf created successfully.")
