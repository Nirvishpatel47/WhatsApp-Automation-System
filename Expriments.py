from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# Create PDF
pdf = SimpleDocTemplate("bakery_automation_brochure.pdf", pagesize=A4,
                        rightMargin=20*mm, leftMargin=20*mm,
                        topMargin=20*mm, bottomMargin=20*mm)

# Container for elements
elements = []

# Styles
styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=28,
    textColor=colors.HexColor('#2c3e50'),
    spaceAfter=12,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

tagline_style = ParagraphStyle(
    'Tagline',
    parent=styles['Normal'],
    fontSize=14,
    textColor=colors.HexColor('#7f8c8d'),
    spaceAfter=20,
    alignment=TA_CENTER,
    fontName='Helvetica'
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=18,
    textColor=colors.HexColor('#2c3e50'),
    spaceAfter=12,
    spaceBefore=16,
    fontName='Helvetica-Bold',
    leftIndent=10
)

subheading_style = ParagraphStyle(
    'CustomSubHeading',
    parent=styles['Heading3'],
    fontSize=14,
    textColor=colors.HexColor('#34495e'),
    spaceAfter=8,
    spaceBefore=12,
    fontName='Helvetica-Bold'
)

body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['Normal'],
    fontSize=11,
    textColor=colors.HexColor('#333333'),
    spaceAfter=10,
    alignment=TA_JUSTIFY,
    fontName='Helvetica'
)

bullet_style = ParagraphStyle(
    'CustomBullet',
    parent=styles['Normal'],
    fontSize=10,
    textColor=colors.HexColor('#333333'),
    spaceAfter=6,
    leftIndent=20,
    fontName='Helvetica'
)

# Title Page
elements.append(Spacer(1, 30*mm))
elements.append(Paragraph("WhatsApp Order Automation", title_style))
elements.append(Paragraph("for Bakeries", title_style))
elements.append(Spacer(1, 10*mm))
elements.append(Paragraph("Increase repeat orders. Reduce manual work. Simplify customer communication.", tagline_style))
elements.append(Spacer(1, 20*mm))

# Horizontal line
line_table = Table([['']], colWidths=[170*mm])
line_table.setStyle(TableStyle([
    ('LINEABOVE', (0,0), (-1,0), 2, colors.HexColor('#3498db')),
]))
elements.append(line_table)
elements.append(Spacer(1, 10*mm))

# Business Overview
elements.append(Paragraph("Business Overview", heading_style))
elements.append(Paragraph("I build automation tools for local businesses, currently focused on bakeries.", body_style))
elements.append(Paragraph("<b>My Goal:</b> Help bakery owners increase repeat orders, reduce manual work, and simplify customer communication through intelligent automation.", body_style))
elements.append(Paragraph("The system is already built and deployed on Google Cloud Run. It's ready to use.", body_style))
elements.append(Spacer(1, 8*mm))

# What Is This Product
elements.append(Paragraph("What Is This Product?", heading_style))
elements.append(Paragraph("A WhatsApp-based order automation system that handles customer orders, manages pre-orders, sends reminders, and provides a business dashboard—all without requiring bakery owners to manage any technology.", body_style))
elements.append(Paragraph("Your customers text your bakery's WhatsApp number. The system handles everything else.", body_style))
elements.append(Spacer(1, 8*mm))

# Page Break
elements.append(PageBreak())

# Core Features
elements.append(Paragraph("Core Features", heading_style))
elements.append(Spacer(1, 3*mm))

elements.append(Paragraph("Order Management", subheading_style))
elements.append(Paragraph("• WhatsApp-based ordering system", bullet_style))
elements.append(Paragraph("• Custom cake ordering with detail capture", bullet_style))
elements.append(Paragraph("• Pre-order system with automatic date and time extraction", bullet_style))
elements.append(Paragraph("• Order history tracking", bullet_style))
elements.append(Paragraph("• Payment confirmation (manual or automatic)", bullet_style))
elements.append(Spacer(1, 3*mm))

elements.append(Paragraph("Communication Tools", subheading_style))
elements.append(Paragraph("• Customer chat interface (two-way communication)", bullet_style))
elements.append(Paragraph("• Automatic reminders for pickup/delivery", bullet_style))
elements.append(Paragraph("• Repeat order nudges to increase sales", bullet_style))
elements.append(Paragraph("• Quick-reply templates for common questions", bullet_style))
elements.append(Spacer(1, 3*mm))

elements.append(Paragraph("Business Dashboard", subheading_style))
elements.append(Paragraph("• View all orders in one place", bullet_style))
elements.append(Paragraph("• Track order status", bullet_style))
elements.append(Paragraph("• Monitor customer interactions", bullet_style))
elements.append(Paragraph("• Access complete order history", bullet_style))
elements.append(Spacer(1, 3*mm))

elements.append(Paragraph("Scalability", subheading_style))
elements.append(Paragraph("• Multi-branch support for bakery chains", bullet_style))
elements.append(Paragraph("• Fast setup (ready in days, not weeks)", bullet_style))
elements.append(Paragraph("• Simple verification process", bullet_style))
elements.append(Paragraph("• End-to-end automation", bullet_style))
elements.append(Spacer(1, 8*mm))

# Benefits
elements.append(Paragraph("Benefits for Bakery Owners", heading_style))
elements.append(Spacer(1, 3*mm))

benefits_data = [
    ["<b>More Repeat Orders</b>", "Automated nudges remind customers to reorder their favorites."],
    ["<b>Faster Customer Response</b>", "Instant replies keep customers engaged, even when you're busy baking."],
    ["<b>Lower Workload</b>", "Stop juggling phone calls and note-taking. The system captures everything."],
    ["<b>Higher Customer Satisfaction</b>", "Quick responses and organized orders create better experiences."],
    ["<b>Works Without You</b>", "The system runs 24/7, even when you're closed or away."],
    ["<b>No Learning Curve</b>", "Simple dashboard. No technical knowledge needed."],
    ["<b>Convert App Orders to Direct</b>", "Turn Zomato/Swiggy customers into WhatsApp customers—no commission fees."],
]

benefits_table = Table(benefits_data, colWidths=[55*mm, 115*mm])
benefits_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
]))
elements.append(benefits_table)
elements.append(Spacer(1, 8*mm))

# Page Break
elements.append(PageBreak())

# Pain Points
elements.append(Paragraph("Pain Points This Solves", heading_style))
elements.append(Spacer(1, 3*mm))

pain_points = [
    ["<b>Problem:</b> Too many order calls during peak hours.", "<b>Solution:</b> WhatsApp automation handles orders without phone calls."],
    ["<b>Problem:</b> Custom cake details get mixed up or forgotten.", "<b>Solution:</b> System captures and organizes every detail automatically."],
    ["<b>Problem:</b> Pre-order dates are forgotten, leading to missed orders.", "<b>Solution:</b> Automatic date extraction and reminders."],
    ["<b>Problem:</b> Customers want faster replies.", "<b>Solution:</b> Instant automated responses keep customers happy."],
    ["<b>Problem:</b> High commissions on food delivery apps.", "<b>Solution:</b> Direct WhatsApp orders mean zero commission fees."],
    ["<b>Problem:</b> Complex software systems are too hard to learn.", "<b>Solution:</b> Simple WhatsApp interface—no app installation needed."],
]

pain_table = Table(pain_points, colWidths=[85*mm, 85*mm])
pain_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 10),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
]))
elements.append(pain_table)
elements.append(Spacer(1, 8*mm))

# How It Works
elements.append(Paragraph("How It Works", heading_style))
elements.append(Spacer(1, 3*mm))

workflow_data = [
    ["1", "Customer texts your bakery on WhatsApp"],
    ["2", "System automatically handles the order flow\n• Asks relevant questions\n• Captures order details\n• Extracts dates for pre-orders\n• Confirms customization requests"],
    ["3", "You receive a clear order summary on your dashboard"],
    ["4", "Payment confirmation (manual or automatic based on your preference)"],
    ["5", "System sends automatic reminders to customers"],
    ["6", "Order completed—customer gets nudged for repeat orders"],
]

workflow_table = Table(workflow_data, colWidths=[15*mm, 155*mm])
workflow_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#3498db')),
    ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#f8f9fa')),
    ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
    ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (0, -1), 14),
    ('FONTSIZE', (1, 0), (1, -1), 10),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 10),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ('GRID', (0, 0), (-1, -1), 1, colors.white),
]))
elements.append(workflow_table)
elements.append(Spacer(1, 8*mm))

# Page Break
elements.append(PageBreak())

# Before vs After
elements.append(Paragraph("Before vs After Automation", heading_style))
elements.append(Spacer(1, 3*mm))

comparison_data = [
    ["Before Automation", "After Automation"],
    ["Phone calls interrupt baking", "WhatsApp handles orders silently"],
    ["Order details written on paper", "Digital records, searchable anytime"],
    ["Forgot to remind customers", "Automatic reminders sent"],
    ["Lost repeat customers", "System nudges for reorders"],
    ["Paying 20-30% app commissions", "Direct orders, zero commission"],
    ["Manually replying to every message", "Automated replies for common questions"],
    ["Missed pre-orders", "Never miss a pre-order again"],
]

comparison_table = Table(comparison_data, colWidths=[85*mm, 85*mm])
comparison_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, 0), 12),
    ('FONTSIZE', (0, 1), (-1, -1), 10),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
]))
elements.append(comparison_table)
elements.append(Spacer(1, 8*mm))

# Pricing
elements.append(Paragraph("Pricing", heading_style))
elements.append(Spacer(1, 3*mm))

pricing_data = [
    ["Free Trial", "7–14 days, full access, no credit card required"],
    ["First Month (Limited Offer)", "₹399 only"],
    ["After First Month", "₹999/month"],
]

pricing_table = Table(pricing_data, colWidths=[60*mm, 110*mm])
pricing_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#3498db')),
    ('BACKGROUND', (1, 0), (1, -1), colors.white),
    ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
    ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 11),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 10),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
]))
elements.append(pricing_table)
elements.append(Spacer(1, 5*mm))

elements.append(Paragraph("<b>What You Get:</b>", body_style))
elements.append(Paragraph("• Full system access", bullet_style))
elements.append(Paragraph("• Unlimited orders", bullet_style))
elements.append(Paragraph("• Dashboard access", bullet_style))
elements.append(Paragraph("• Automatic updates", bullet_style))
elements.append(Paragraph("• Customer support", bullet_style))
elements.append(Spacer(1, 3*mm))
elements.append(Paragraph("<b>No Hidden Costs. No Setup Fees. Cancel Anytime.</b>", body_style))
elements.append(Spacer(1, 8*mm))

# Who Am I
elements.append(Paragraph("Who Am I?", heading_style))
elements.append(Paragraph("I'm a teen founder and diploma student who builds automation products for local businesses.", body_style))
elements.append(Spacer(1, 3*mm))
elements.append(Paragraph("<b>Why Trust Me?</b>", body_style))
elements.append(Paragraph("• The system is already fully built and deployed", bullet_style))
elements.append(Paragraph("• Fast at development and problem-solving", bullet_style))
elements.append(Paragraph("• Serious about long-term product building", bullet_style))
elements.append(Paragraph("• Focused on creating real value for small businesses", bullet_style))
elements.append(Spacer(1, 3*mm))
elements.append(Paragraph("This isn't a side project. This is a professional product built to help bakeries grow.", body_style))
elements.append(Spacer(1, 8*mm))

# Contact Section
elements.append(Paragraph("Get Started Today", heading_style))
elements.append(Spacer(1, 3*mm))

contact_data = [
    ["WhatsApp", "[Your WhatsApp Number]"],
    ["Email", "[Your Email Address]"],
    ["Instagram", "@[Your Instagram Handle]"],
    ["Website", "[Your Website/Domain]"],
]

contact_table = Table(contact_data, colWidths=[40*mm, 130*mm])
contact_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 11),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
]))
elements.append(contact_table)
elements.append(Spacer(1, 10*mm))

# Footer
footer_style = ParagraphStyle(
    'Footer',
    parent=styles['Normal'],
    fontSize=12,
    textColor=colors.HexColor('#2c3e50'),
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)
elements.append(Paragraph("Ready to Automate Your Bakery?", footer_style))
elements.append(Spacer(1, 2*mm))
elements.append(Paragraph("Contact me for a free trial and see the difference automation makes.", body_style))

# Build PDF
pdf.build(elements)
print("PDF created successfully: bakery_automation_brochure.pdf")